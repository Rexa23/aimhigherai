"""
CRUD layer for Lead model. All DB access goes through here — no raw queries in routes.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lead import (
    Chain, EventType, FollowUp, Lead, LeadEvent, LeadMemory,
    LeadPriority, LeadStage, Message, Conversation, OutreachChannel,
)
from app.schemas.lead import LeadCreate, LeadUpdate


# ── Lead ──────────────────────────────────────────────────────────────────────

async def get_lead(db: AsyncSession, lead_id: uuid.UUID) -> Lead | None:
    result = await db.execute(
        select(Lead)
        .options(selectinload(Lead.memory))
        .where(Lead.id == lead_id, Lead.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_lead_with_conversations(db: AsyncSession, lead_id: uuid.UUID) -> Lead | None:
    result = await db.execute(
        select(Lead)
        .options(
            selectinload(Lead.conversations).selectinload(Conversation.messages),
            selectinload(Lead.memory),
            selectinload(Lead.events),
        )
        .where(Lead.id == lead_id, Lead.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_leads(
    db: AsyncSession,
    *,
    stage: LeadStage | None = None,
    priority: LeadPriority | None = None,
    chain: Chain | None = None,
    min_score: float | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Lead], int]:
    query = select(Lead).where(Lead.is_deleted == False)
    if stage:
        query = query.where(Lead.stage == stage)
    if priority:
        query = query.where(Lead.priority == priority)
    if chain:
        query = query.where(Lead.chain == chain)
    if min_score is not None:
        query = query.where(Lead.score >= min_score)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    query = query.order_by(Lead.score.desc(), Lead.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all(), total


async def create_lead(db: AsyncSession, payload: LeadCreate) -> Lead:
    lead = Lead(**payload.model_dump())
    db.add(lead)
    await db.flush()
    # Create empty memory record
    memory = LeadMemory(lead_id=lead.id)
    db.add(memory)
    await db.flush()
    return lead


async def upsert_lead(db: AsyncSession, payload: LeadCreate) -> tuple[Lead, bool]:
    """Insert or update by (contract_address, chain). Returns (lead, created)."""
    existing = None
    if payload.contract_address:
        result = await db.execute(
            select(Lead).where(
                Lead.contract_address == payload.contract_address,
                Lead.chain == payload.chain,
                Lead.is_deleted == False,
            )
        )
        existing = result.scalar_one_or_none()

    if existing:
        # Update score and market data, preserve stage
        existing.score = max(existing.score, payload.score)
        existing.market_cap_usd = payload.market_cap_usd
        existing.activity_metrics = payload.activity_metrics
        existing.pain_signals = list(set(existing.pain_signals + payload.pain_signals))
        existing.last_activity_at = datetime.utcnow()
        if payload.score > existing.score:
            existing.priority = payload.priority
        await db.flush()
        return existing, False

    lead = await create_lead(db, payload)
    return lead, True


async def update_lead(db: AsyncSession, lead: Lead, data: LeadUpdate) -> Lead:
    updates = data.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(lead, key, value)
    lead.updated_at = datetime.utcnow()
    await db.flush()
    return lead


async def transition_stage(
    db: AsyncSession,
    lead: Lead,
    new_stage: LeadStage,
    reason: str | None = None,
) -> Lead:
    old_stage = lead.stage
    lead.stage = new_stage
    if new_stage == LeadStage.CONVERTED:
        lead.converted_at = datetime.utcnow()
    lead.updated_at = datetime.utcnow()
    await db.flush()

    event = LeadEvent(
        lead_id=lead.id,
        event_type=EventType.STAGE_CHANGE,
        payload={"from": old_stage, "to": new_stage, "reason": reason},
    )
    db.add(event)
    await db.flush()
    return lead


async def soft_delete_lead(db: AsyncSession, lead: Lead) -> None:
    lead.is_deleted = True
    await db.flush()


# ── Events ────────────────────────────────────────────────────────────────────

async def log_event(
    db: AsyncSession,
    lead_id: uuid.UUID,
    event_type: EventType,
    payload: dict[str, Any],
) -> LeadEvent:
    event = LeadEvent(lead_id=lead_id, event_type=event_type, payload=payload)
    db.add(event)
    await db.flush()
    return event


async def get_lead_events(
    db: AsyncSession,
    lead_id: uuid.UUID,
    limit: int = 100,
) -> list[LeadEvent]:
    result = await db.execute(
        select(LeadEvent)
        .where(LeadEvent.lead_id == lead_id)
        .order_by(LeadEvent.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


# ── Conversations & Messages ───────────────────────────────────────────────────

async def get_or_create_conversation(
    db: AsyncSession,
    lead_id: uuid.UUID,
    channel: OutreachChannel,
    external_thread_id: str | None = None,
) -> tuple[Conversation, bool]:
    result = await db.execute(
        select(Conversation).where(
            Conversation.lead_id == lead_id,
            Conversation.channel == channel,
            Conversation.is_active == True,
        )
    )
    conv = result.scalar_one_or_none()
    if conv:
        return conv, False

    conv = Conversation(
        lead_id=lead_id,
        channel=channel,
        external_thread_id=external_thread_id,
    )
    db.add(conv)
    await db.flush()
    return conv, True


async def add_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    direction: str,
    content: str,
    ai_generated: bool = True,
    model_used: str | None = None,
    raw_payload: dict | None = None,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        direction=direction,
        content=content,
        ai_generated=ai_generated,
        model_used=model_used,
        raw_payload=raw_payload or {},
    )
    db.add(msg)
    # Update last_message_at on conversation
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(last_message_at=datetime.utcnow())
    )
    await db.flush()
    return msg


async def get_conversation_messages(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    limit: int = 50,
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    return result.scalars().all()


# ── Memory ────────────────────────────────────────────────────────────────────

async def update_lead_memory(
    db: AsyncSession,
    lead_id: uuid.UUID,
    summary: str | None = None,
    key_facts: dict | None = None,
    recent_turns: list | None = None,
) -> LeadMemory:
    result = await db.execute(
        select(LeadMemory).where(LeadMemory.lead_id == lead_id)
    )
    memory = result.scalar_one_or_none()
    if not memory:
        memory = LeadMemory(lead_id=lead_id)
        db.add(memory)

    if summary is not None:
        memory.summary = summary
    if key_facts is not None:
        memory.key_facts = {**memory.key_facts, **key_facts}
    if recent_turns is not None:
        memory.recent_turns = recent_turns[-20:]  # keep last 20 turns
    memory.updated_at = datetime.utcnow()
    await db.flush()
    return memory


# ── Follow-ups ────────────────────────────────────────────────────────────────

async def create_followup(
    db: AsyncSession,
    lead_id: uuid.UUID,
    channel: OutreachChannel,
    message_template: str,
    scheduled_at: datetime,
) -> FollowUp:
    followup = FollowUp(
        lead_id=lead_id,
        channel=channel,
        message_template=message_template,
        scheduled_at=scheduled_at,
    )
    db.add(followup)
    await db.flush()
    return followup


async def get_due_followups(db: AsyncSession) -> list[FollowUp]:
    result = await db.execute(
        select(FollowUp)
        .where(
            FollowUp.is_sent == False,
            FollowUp.is_cancelled == False,
            FollowUp.scheduled_at <= datetime.utcnow(),
        )
        .order_by(FollowUp.scheduled_at.asc())
        .limit(100)
    )
    return result.scalars().all()


# ── Analytics ─────────────────────────────────────────────────────────────────

async def get_dashboard_stats(db: AsyncSession) -> dict[str, Any]:
    # Stage distribution
    stage_result = await db.execute(
        select(Lead.stage, func.count(Lead.id))
        .where(Lead.is_deleted == False)
        .group_by(Lead.stage)
    )
    by_stage = {row[0]: row[1] for row in stage_result.all()}

    # Priority distribution
    priority_result = await db.execute(
        select(Lead.priority, func.count(Lead.id))
        .where(Lead.is_deleted == False)
        .group_by(Lead.priority)
    )
    by_priority = {row[0]: row[1] for row in priority_result.all()}

    # Chain distribution
    chain_result = await db.execute(
        select(Lead.chain, func.count(Lead.id))
        .where(Lead.is_deleted == False)
        .group_by(Lead.chain)
    )
    by_chain = {row[0]: row[1] for row in chain_result.all()}

    # Total and conversions
    total_result = await db.execute(
        select(func.count(Lead.id)).where(Lead.is_deleted == False)
    )
    total = total_result.scalar_one()

    converted = by_stage.get(LeadStage.CONVERTED, 0)
    conversion_rate = (converted / total * 100) if total > 0 else 0.0

    # Avg score
    avg_result = await db.execute(
        select(func.avg(Lead.score)).where(Lead.is_deleted == False)
    )
    avg_score = float(avg_result.scalar_one() or 0.0)

    # 7-day window stats
    cutoff = datetime.utcnow() - timedelta(days=7)
    new_7d_result = await db.execute(
        select(func.count(Lead.id))
        .where(Lead.is_deleted == False, Lead.created_at >= cutoff)
    )
    new_leads_7d = new_7d_result.scalar_one()

    converted_7d_result = await db.execute(
        select(func.count(Lead.id))
        .where(Lead.is_deleted == False, Lead.converted_at >= cutoff)
    )
    converted_7d = converted_7d_result.scalar_one()

    # Messages 7d
    msgs_result = await db.execute(
        select(func.count(Message.id))
        .where(Message.direction == "outbound", Message.created_at >= cutoff)
    )
    messages_sent_7d = msgs_result.scalar_one()

    replies_result = await db.execute(
        select(func.count(Message.id))
        .where(Message.direction == "inbound", Message.created_at >= cutoff)
    )
    replies_received_7d = replies_result.scalar_one()

    return {
        "total_leads": total,
        "by_stage": by_stage,
        "by_priority": by_priority,
        "by_chain": by_chain,
        "conversion_rate": round(conversion_rate, 2),
        "avg_score": round(avg_score, 2),
        "messages_sent_7d": messages_sent_7d,
        "replies_received_7d": replies_received_7d,
        "new_leads_7d": new_leads_7d,
        "converted_7d": converted_7d,
    }
