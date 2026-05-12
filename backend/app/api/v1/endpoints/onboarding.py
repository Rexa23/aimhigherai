"""
/api/v1/onboarding — interactive step endpoint, progress viewer, manual controls
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.db.crud import get_lead, get_lead_with_conversations
from app.db.session import get_db
from app.core.redis import QueueName, enqueue, get_redis
from app.agents.onboarding import ONBOARDING_STEPS, generate_onboarding_response
from app.agents.qualification_worker import QualificationWorker
from app.schemas.lead import OnboardingStepRequest, OnboardingStepResponse
from app.models.lead import LeadStage

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

DbDep    = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]


@router.post("/chat", response_model=OnboardingStepResponse)
async def onboarding_chat(payload: OnboardingStepRequest, db: DbDep, redis: RedisDep):
    """
    Process an inbound message from a lead during onboarding.
    Returns the agent's reply, sources, and updated step.
    Can be called directly from the dashboard chat panel.
    """
    lead = await get_lead_with_conversations(db, payload.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.stage != LeadStage.ONBOARDING:
        raise HTTPException(
            status_code=400,
            detail=f"Lead is in stage {lead.stage!r}, not onboarding",
        )

    history = QualificationWorker._flatten_conversations(lead.conversations)
    lead_data = {
        "project_name":    lead.project_name,
        "chain":           lead.chain,
        "market_cap_usd":  lead.market_cap_usd,
        "score":           lead.score,
        "priority":        lead.priority,
        "pain_signals":    lead.pain_signals,
        "stage":           lead.stage,
        "qualification_data": lead.qualification_data,
        "memory_summary":  lead.memory.summary if lead.memory else None,
        "key_facts":       lead.memory.key_facts if lead.memory else {},
    }

    result = await generate_onboarding_response(
        lead=lead_data,
        conversation_history=history,
        user_message=payload.user_message,
        current_step=lead.onboarding_step or 0,
    )

    # Queue the DB writes asynchronously
    active_conv = next((c for c in lead.conversations if c.is_active), None)
    if active_conv:
        await enqueue(redis, QueueName.ONBOARDING_TASKS, {
            "type":            "onboarding_reply",
            "lead_id":         str(payload.lead_id),
            "conversation_id": str(active_conv.id),
            "user_message":    payload.user_message,
        })

    return OnboardingStepResponse(
        lead_id=payload.lead_id,
        step=result["next_step"],
        reply=result["reply"],
        sources_used=result["sources_used"],
        next_action=result.get("next_action"),
    )


@router.get("/{lead_id}/progress")
async def get_onboarding_progress(lead_id: uuid.UUID, db: DbDep):
    lead = await get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    current_step = lead.onboarding_step or 0
    steps_summary = [
        {
            "step":      s["step"],
            "name":      s["name"],
            "goal":      s["goal"],
            "status":    "completed" if s["step"] < current_step
                         else "current" if s["step"] == current_step
                         else "pending",
        }
        for s in ONBOARDING_STEPS
    ]

    return {
        "lead_id":      lead_id,
        "project_name": lead.project_name,
        "stage":        lead.stage,
        "current_step": current_step,
        "total_steps":  len(ONBOARDING_STEPS),
        "pct_complete": round(current_step / len(ONBOARDING_STEPS) * 100),
        "steps":        steps_summary,
    }


@router.post("/{lead_id}/advance")
async def force_advance_step(lead_id: uuid.UUID, redis: RedisDep, db: DbDep):
    """Force-advance to the next onboarding step (operator override)."""
    lead = await get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.stage != LeadStage.ONBOARDING:
        raise HTTPException(status_code=400, detail="Lead is not in onboarding")

    await enqueue(redis, QueueName.ONBOARDING_TASKS, {
        "type":    "advance_step",
        "lead_id": str(lead_id),
    })
    return {"status": "queued", "current_step": lead.onboarding_step}


@router.post("/{lead_id}/start")
async def start_onboarding(lead_id: uuid.UUID, redis: RedisDep, db: DbDep):
    """Manually start onboarding for a qualified lead."""
    lead = await get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.stage != LeadStage.QUALIFIED:
        raise HTTPException(status_code=400, detail=f"Lead must be in QUALIFIED stage, got {lead.stage!r}")

    await enqueue(redis, QueueName.ONBOARDING_TASKS, {
        "type":    "start_onboarding",
        "lead_id": str(lead_id),
    })
    return {"status": "queued"}
