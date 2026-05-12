"""
/api/v1/leads — full CRUD + stage transitions + events + conversations
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud import (
    create_lead, get_lead, get_lead_with_conversations, get_leads,
    get_lead_events, log_event, soft_delete_lead, transition_stage, update_lead,
)
from app.db.session import get_db
from app.models.lead import Chain, EventType, LeadPriority, LeadStage
from app.schemas.lead import (
    EventOut, LeadCreate, LeadListOut, LeadOut,
    LeadStageTransition, LeadUpdate, ConversationWithMessages,
)

router = APIRouter(prefix="/leads", tags=["leads"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=LeadListOut)
async def list_leads(
    db: DbDep,
    stage: LeadStage | None = Query(None),
    priority: LeadPriority | None = Query(None),
    chain: Chain | None = Query(None),
    min_score: float | None = Query(None, ge=0, le=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    leads, total = await get_leads(
        db, stage=stage, priority=priority,
        chain=chain, min_score=min_score,
        page=page, page_size=page_size,
    )
    return LeadListOut(total=total, page=page, page_size=page_size, items=leads)


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def create_lead_route(db: DbDep, payload: LeadCreate):
    lead = await create_lead(db, payload)
    await log_event(db, lead.id, EventType.STAGE_CHANGE, {"from": None, "to": "discovered"})
    return lead


# ── Get ───────────────────────────────────────────────────────────────────────

@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead_route(lead_id: uuid.UUID, db: DbDep):
    lead = await get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead_route(lead_id: uuid.UUID, payload: LeadUpdate, db: DbDep):
    lead = await get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return await update_lead(db, lead, payload)


# ── Stage transition ──────────────────────────────────────────────────────────

@router.post("/{lead_id}/transition", response_model=LeadOut)
async def transition_lead_stage(
    lead_id: uuid.UUID,
    payload: LeadStageTransition,
    db: DbDep,
):
    lead = await get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Enforce valid forward transitions
    valid_transitions: dict[LeadStage, list[LeadStage]] = {
        LeadStage.DISCOVERED:    [LeadStage.CONTACTED, LeadStage.DISQUALIFIED, LeadStage.DEAD],
        LeadStage.CONTACTED:     [LeadStage.QUALIFIED, LeadStage.DISQUALIFIED, LeadStage.DEAD],
        LeadStage.QUALIFIED:     [LeadStage.ONBOARDING, LeadStage.DISQUALIFIED, LeadStage.DEAD],
        LeadStage.ONBOARDING:    [LeadStage.CONVERTED, LeadStage.DISQUALIFIED, LeadStage.DEAD],
        LeadStage.CONVERTED:     [],
        LeadStage.DISQUALIFIED:  [LeadStage.DISCOVERED],  # allow re-activation
        LeadStage.DEAD:          [LeadStage.DISCOVERED],
    }
    allowed = valid_transitions.get(lead.stage, [])
    if payload.stage not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {lead.stage} to {payload.stage}. Allowed: {[s.value for s in allowed]}",
        )

    return await transition_stage(db, lead, payload.stage, payload.reason)


# ── Conversations ─────────────────────────────────────────────────────────────

@router.get("/{lead_id}/conversations", response_model=list[ConversationWithMessages])
async def get_lead_conversations(lead_id: uuid.UUID, db: DbDep):
    lead = await get_lead_with_conversations(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead.conversations


# ── Events ────────────────────────────────────────────────────────────────────

@router.get("/{lead_id}/events", response_model=list[EventOut])
async def get_events(
    lead_id: uuid.UUID,
    db: DbDep,
    limit: int = Query(100, ge=1, le=500),
):
    lead = await get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return await get_lead_events(db, lead_id, limit=limit)


# ── Soft delete ───────────────────────────────────────────────────────────────

@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead_route(lead_id: uuid.UUID, db: DbDep):
    lead = await get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await soft_delete_lead(db, lead)
