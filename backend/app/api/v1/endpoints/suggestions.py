"""
/api/v1/suggestions — AI reply suggestions for the dashboard chat panel.
Also: stream a reply in real-time for the conversation view.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud import get_lead, get_conversation_messages
from app.db.session import get_db
from app.models.lead import MessageDirection
from app.services.outreach_composer import generate_suggestions, generate_reply
from app.services.gemini_client import stream_complete, format_lead_context, build_conversation_messages

router = APIRouter(prefix="/suggestions", tags=["suggestions"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


class SuggestionsRequest(BaseModel):
    lead_id: uuid.UUID
    conversation_id: uuid.UUID
    last_inbound: str


class StreamReplyRequest(BaseModel):
    lead_id: uuid.UUID
    conversation_id: uuid.UUID
    inbound_message: str


@router.post("")
async def get_suggestions(payload: SuggestionsRequest, db: DbDep):
    lead = await get_lead(db, payload.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    msgs = await get_conversation_messages(db, payload.conversation_id, limit=12)
    history = [
        {"role": "user" if m.direction == MessageDirection.INBOUND else "assistant",
         "content": m.content}
        for m in msgs
    ]

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

    suggestions = await generate_suggestions(lead_data, history, payload.last_inbound)
    return {"suggestions": suggestions}


@router.post("/stream")
async def stream_reply(payload: StreamReplyRequest, db: DbDep):
    """Stream a reply token-by-token for the live dashboard chat view."""
    lead = await get_lead(db, payload.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    msgs = await get_conversation_messages(db, payload.conversation_id, limit=16)
    history = [
        {"role": "user" if m.direction == MessageDirection.INBOUND else "assistant",
         "content": m.content}
        for m in msgs
    ]

    from app.services.outreach_composer import OUTREACH_SYSTEM
    from app.services.gemini_client import format_lead_context

    lead_ctx = format_lead_context({
        "project_name":  lead.project_name,
        "chain":         lead.chain,
        "market_cap_usd": lead.market_cap_usd,
        "score":         lead.score,
        "priority":      lead.priority,
        "pain_signals":  lead.pain_signals,
        "memory_summary": lead.memory.summary if lead.memory else None,
    })

    system = OUTREACH_SYSTEM + f"\n\nLEAD CONTEXT:\n{lead_ctx}"
    messages = build_conversation_messages(history, payload.inbound_message)

    async def token_generator():
        async for token in stream_complete(system, messages, max_tokens=400):
            yield token

    return StreamingResponse(token_generator(), media_type="text/plain")
