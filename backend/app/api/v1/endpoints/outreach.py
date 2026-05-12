"""
/api/v1/outreach — trigger outreach, ingest replies, manage follow-ups
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud import (
    get_lead, get_or_create_conversation, add_message,
    create_followup, get_due_followups, log_event,
)
from app.db.session import get_db
from app.core.redis import QueueName, enqueue, get_redis
from app.models.lead import EventType, MessageDirection, OutreachChannel
from app.schemas.lead import (
    ConversationOut, FollowUpCreate, FollowUpOut,
    OutreachRequest, OutreachResult, ReplyIngest,
)
import redis.asyncio as aioredis

router = APIRouter(prefix="/outreach", tags=["outreach"])

DbDep    = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]


# ── Trigger outreach ──────────────────────────────────────────────────────────

@router.post("/send", response_model=OutreachResult)
async def send_outreach(
    payload: OutreachRequest,
    db: DbDep,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
):
    lead = await get_lead(db, payload.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    conv, _ = await get_or_create_conversation(db, payload.lead_id, payload.channel)

    task_id = await enqueue(redis, QueueName.OUTREACH_TASKS, {
        "lead_id": str(payload.lead_id),
        "channel": payload.channel.value,
        "conversation_id": str(conv.id),
        "custom_note": payload.custom_note,
    })

    await log_event(db, payload.lead_id, EventType.OUTREACH_SENT, {
        "channel": payload.channel.value,
        "task_id": task_id,
    })

    return OutreachResult(
        lead_id=payload.lead_id,
        channel=payload.channel,
        message="",           # populated after worker processes
        conversation_id=conv.id,
        status="queued",
    )


# ── Ingest inbound reply (called by webhook handlers) ────────────────────────

@router.post("/reply")
async def ingest_reply(payload: ReplyIngest, db: DbDep, redis: RedisDep):
    """
    Webhook endpoint called by Twitter/Telegram/Discord bots when a reply arrives.
    Looks up the conversation, stores the message, and queues an AI response task.
    """
    from sqlalchemy import select
    from app.models.lead import Conversation

    result = await db.execute(
        select(Conversation).where(
            Conversation.external_thread_id == payload.external_thread_id,
            Conversation.channel == payload.platform,
            Conversation.is_active == True,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="No active conversation for this thread")

    msg = await add_message(
        db,
        conversation_id=conv.id,
        direction=MessageDirection.INBOUND,
        content=payload.content,
        ai_generated=False,
        raw_payload=payload.raw_payload,
    )

    await log_event(db, conv.lead_id, EventType.REPLY_RECEIVED, {
        "channel": payload.platform.value,
        "sender": payload.sender_handle,
        "message_id": str(msg.id),
    })

    # Queue AI response generation
    await enqueue(redis, QueueName.OUTREACH_TASKS, {
        "type": "reply",
        "lead_id": str(conv.lead_id),
        "conversation_id": str(conv.id),
        "channel": payload.platform.value,
        "inbound_message": payload.content,
    })

    return {"status": "queued", "message_id": str(msg.id)}


# ── Follow-ups ────────────────────────────────────────────────────────────────

@router.post("/followups", response_model=FollowUpOut, status_code=201)
async def schedule_followup(payload: FollowUpCreate, db: DbDep, redis: RedisDep):
    lead = await get_lead(db, payload.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    followup = await create_followup(
        db,
        lead_id=payload.lead_id,
        channel=payload.channel,
        message_template=payload.message_template,
        scheduled_at=payload.scheduled_at,
    )

    from app.core.redis import ScheduleKey, schedule_task
    await schedule_task(redis, ScheduleKey.FOLLOWUPS, {
        "followup_id": str(followup.id),
        "lead_id": str(payload.lead_id),
        "channel": payload.channel.value,
    }, run_at=payload.scheduled_at)

    return followup


@router.get("/followups/due", response_model=list[FollowUpOut])
async def list_due_followups(db: DbDep):
    return await get_due_followups(db)


# ── Conversations by lead ─────────────────────────────────────────────────────

@router.get("/conversations/{lead_id}", response_model=list[ConversationOut])
async def get_conversations(lead_id: uuid.UUID, db: DbDep):
    lead = await get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    from sqlalchemy import select
    from app.models.lead import Conversation
    result = await db.execute(
        select(Conversation).where(Conversation.lead_id == lead_id)
        .order_by(Conversation.created_at.desc())
    )
    return result.scalars().all()
