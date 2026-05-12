"""
/api/v1/qualification — manual trigger, result viewer, objection response generator
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
from app.models.lead import MessageDirection
from app.schemas.lead import QualificationResult
from app.agents.qualification import extract_qualification, generate_objection_response

router = APIRouter(prefix="/qualification", tags=["qualification"])

DbDep    = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]


@router.post("/{lead_id}/run", response_model=QualificationResult)
async def run_qualification(lead_id: uuid.UUID, db: DbDep, redis: RedisDep):
    """Manually trigger qualification for a lead. Queues the worker task."""
    lead = await get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    await enqueue(redis, QueueName.QUALIFY_TASKS, {
        "lead_id": str(lead_id),
    })
    return {
        "lead_id":             lead_id,
        "qualification_score": lead.qualification_score or 0.0,
        "category":            lead.qualification_data.get("category", "cold"),
        "objections":          lead.qualification_data.get("objections", []),
        "readiness_level":     lead.qualification_data.get("readiness_level", "low"),
        "extracted_data":      lead.qualification_data,
    }


@router.post("/{lead_id}/qualify-now", response_model=QualificationResult)
async def qualify_now(lead_id: uuid.UUID, db: DbDep):
    """Run qualification synchronously and return result immediately (for dashboard use)."""
    lead = await get_lead_with_conversations(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    from app.agents.qualification_worker import QualificationWorker
    history = QualificationWorker._flatten_conversations(lead.conversations)

    lead_data = {
        "project_name":  lead.project_name,
        "chain":         lead.chain,
        "market_cap_usd": lead.market_cap_usd,
        "score":         lead.score,
        "priority":      lead.priority,
        "pain_signals":  lead.pain_signals,
        "stage":         lead.stage,
        "memory_summary": lead.memory.summary if lead.memory else None,
        "key_facts":     lead.memory.key_facts if lead.memory else {},
    }

    result = await extract_qualification(lead_data, history)

    return QualificationResult(
        lead_id=lead_id,
        qualification_score=result["qualification_score"],
        category=result["category"],
        objections=result["objections"],
        readiness_level=result["readiness_level"],
        extracted_data=result["extracted_data"],
    )


@router.get("/{lead_id}/result", response_model=QualificationResult)
async def get_qualification_result(lead_id: uuid.UUID, db: DbDep):
    lead = await get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.qualification_data:
        raise HTTPException(status_code=404, detail="Lead not yet qualified")

    return QualificationResult(
        lead_id=lead_id,
        qualification_score=lead.qualification_score or 0.0,
        category=lead.qualification_data.get("category", "cold"),
        objections=lead.qualification_data.get("objections", []),
        readiness_level=lead.qualification_data.get("readiness_level", "low"),
        extracted_data=lead.qualification_data,
    )


class ObjectionRequest(BaseModel):
    objection: str
    conversation_history: list[dict] = []


@router.post("/{lead_id}/handle-objection")
async def handle_objection(lead_id: uuid.UUID, payload: ObjectionRequest, db: DbDep):
    """Generate an objection-handling response for the dashboard AI panel."""
    lead = await get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead_data = {
        "project_name":  lead.project_name,
        "chain":         lead.chain,
        "market_cap_usd": lead.market_cap_usd,
        "pain_signals":  lead.pain_signals,
        "qualification_data": lead.qualification_data,
    }

    response = await generate_objection_response(
        objection=payload.objection,
        lead=lead_data,
        conversation_history=payload.conversation_history,
    )
    return {"response": response, "objection": payload.objection}
