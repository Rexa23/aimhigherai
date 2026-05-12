"""
Pydantic v2 schemas — request bodies, response models, internal payloads.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from app.models.lead import Chain, EventType, LeadPriority, LeadStage, MessageDirection, OutreachChannel


# ── Shared ────────────────────────────────────────────────────────────────────

class OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Lead schemas ──────────────────────────────────────────────────────────────

class LeadCreate(BaseModel):
    project_name: str
    chain: Chain
    token_symbol: str | None = None
    contract_address: str | None = None
    website: str | None = None
    contact_links: dict[str, str] = Field(default_factory=dict)
    market_cap_usd: float | None = None
    price_usd: float | None = None
    volume_24h_usd: float | None = None
    liquidity_usd: float | None = None
    score: float = 0.0
    priority: LeadPriority = LeadPriority.COLD
    pain_signals: list[str] = Field(default_factory=list)
    activity_metrics: dict[str, Any] = Field(default_factory=dict)
    source_platform: str | None = None
    source_url: str | None = None


class LeadUpdate(BaseModel):
    project_name: str | None = None
    stage: LeadStage | None = None
    score: float | None = None
    priority: LeadPriority | None = None
    market_cap_usd: float | None = None
    qualification_score: float | None = None
    qualification_data: dict[str, Any] | None = None
    onboarding_step: int | None = None
    onboarding_data: dict[str, Any] | None = None
    pain_signals: list[str] | None = None
    activity_metrics: dict[str, Any] | None = None
    contact_links: dict[str, str] | None = None


class LeadOut(OrmBase):
    id: uuid.UUID
    project_name: str
    token_symbol: str | None
    chain: Chain
    contract_address: str | None
    website: str | None
    contact_links: dict[str, str]
    market_cap_usd: float | None
    score: float
    priority: LeadPriority
    stage: LeadStage
    pain_signals: list[str]
    activity_metrics: dict[str, Any]
    qualification_score: float | None
    qualification_data: dict[str, Any]
    onboarding_step: int
    source_platform: str | None
    first_seen_at: datetime
    last_activity_at: datetime
    converted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LeadListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[LeadOut]


class LeadStageTransition(BaseModel):
    stage: LeadStage
    reason: str | None = None


# ── Conversation / Message schemas ────────────────────────────────────────────

class ConversationCreate(BaseModel):
    lead_id: uuid.UUID
    channel: OutreachChannel
    external_thread_id: str | None = None


class ConversationOut(OrmBase):
    id: uuid.UUID
    lead_id: uuid.UUID
    channel: OutreachChannel
    external_thread_id: str | None
    is_active: bool
    created_at: datetime
    last_message_at: datetime | None


class MessageCreate(BaseModel):
    conversation_id: uuid.UUID
    direction: MessageDirection
    content: str
    ai_generated: bool = True
    model_used: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class MessageOut(OrmBase):
    id: uuid.UUID
    conversation_id: uuid.UUID
    direction: MessageDirection
    content: str
    ai_generated: bool
    model_used: str | None
    created_at: datetime


class ConversationWithMessages(ConversationOut):
    messages: list[MessageOut] = Field(default_factory=list)


# ── Outreach schemas ──────────────────────────────────────────────────────────

class OutreachRequest(BaseModel):
    lead_id: uuid.UUID
    channel: OutreachChannel
    custom_note: str | None = None   # optional human override hint


class OutreachResult(BaseModel):
    lead_id: uuid.UUID
    channel: OutreachChannel
    message: str
    conversation_id: uuid.UUID
    status: str  # "sent" | "queued" | "failed"
    error: str | None = None


class ReplyIngest(BaseModel):
    """Webhook payload from Twitter/Telegram/Discord for inbound replies."""
    platform: OutreachChannel
    external_thread_id: str
    sender_handle: str
    content: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)


# ── Qualification schemas ─────────────────────────────────────────────────────

class QualificationResult(BaseModel):
    lead_id: uuid.UUID
    qualification_score: float = Field(ge=0.0, le=100.0)
    category: LeadPriority
    objections: list[str]
    readiness_level: str   # "high" | "medium" | "low"
    extracted_data: dict[str, Any] = Field(default_factory=dict)
    # e.g. confirmed_market_cap, community_size, growth_intent


# ── Onboarding schemas ────────────────────────────────────────────────────────

class OnboardingStepRequest(BaseModel):
    lead_id: uuid.UUID
    user_message: str


class OnboardingStepResponse(BaseModel):
    lead_id: uuid.UUID
    step: int
    reply: str
    sources_used: list[str] = Field(default_factory=list)
    next_action: str | None = None  # "schedule_call" | "send_contract" | "pool_creation" | None


# ── Hunter schemas ────────────────────────────────────────────────────────────

class HunterLeadPayload(BaseModel):
    """Raw output from the Hunter Service before DB write."""
    project_name: str
    chain: Chain
    market_cap: float
    contact_links: dict[str, str]
    score: float
    pain_signals: list[str]
    activity_metrics: dict[str, Any]
    priority_level: LeadPriority
    source_platform: str
    source_url: str | None = None
    contract_address: str | None = None
    token_symbol: str | None = None


# ── Follow-up schemas ─────────────────────────────────────────────────────────

class FollowUpCreate(BaseModel):
    lead_id: uuid.UUID
    channel: OutreachChannel
    message_template: str
    scheduled_at: datetime


class FollowUpOut(OrmBase):
    id: uuid.UUID
    lead_id: uuid.UUID
    channel: OutreachChannel
    message_template: str
    scheduled_at: datetime
    sent_at: datetime | None
    is_sent: bool
    is_cancelled: bool
    attempt_count: int


# ── Event schemas ─────────────────────────────────────────────────────────────

class EventOut(OrmBase):
    id: uuid.UUID
    lead_id: uuid.UUID
    event_type: EventType
    payload: dict[str, Any]
    created_at: datetime


# ── Knowledge Base schemas ────────────────────────────────────────────────────

class KnowledgeDocCreate(BaseModel):
    title: str
    source_url: str | None = None
    content: str


class KnowledgeDocOut(OrmBase):
    id: uuid.UUID
    title: str
    source_url: str | None
    is_indexed: bool
    created_at: datetime
    indexed_at: datetime | None


class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchResult(BaseModel):
    chunk: str
    source_title: str
    source_url: str | None
    score: float


# ── Dashboard / Analytics schemas ─────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_leads: int
    by_stage: dict[str, int]
    by_priority: dict[str, int]
    by_chain: dict[str, int]
    conversion_rate: float
    avg_score: float
    messages_sent_7d: int
    replies_received_7d: int
    new_leads_7d: int
    converted_7d: int


class AgentStatus(BaseModel):
    hunter: bool
    outreach: bool
    qualification: bool
    onboarding: bool
    conversion: bool


class AgentToggle(BaseModel):
    agent: str = Field(pattern="^(hunter|outreach|qualification|onboarding|conversion)$")
    enabled: bool
