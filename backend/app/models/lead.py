"""
ORM models for AimHigher AI Onboarding system.
All tables use UUIDs as primary keys and include soft-delete support.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class LeadStage(str, enum.Enum):
    DISCOVERED   = "discovered"
    CONTACTED    = "contacted"
    QUALIFIED    = "qualified"
    ONBOARDING   = "onboarding"
    CONVERTED    = "converted"
    DISQUALIFIED = "disqualified"
    DEAD         = "dead"


class LeadPriority(str, enum.Enum):
    HOT    = "hot"
    WARM   = "warm"
    COLD   = "cold"


class Chain(str, enum.Enum):
    ETHEREUM = "ethereum"
    BNB      = "bnb"
    SOLANA   = "solana"
    BASE     = "base"


class OutreachChannel(str, enum.Enum):
    TWITTER  = "twitter"
    TELEGRAM = "telegram"
    DISCORD  = "discord"


class MessageDirection(str, enum.Enum):
    OUTBOUND = "outbound"
    INBOUND  = "inbound"


class EventType(str, enum.Enum):
    STAGE_CHANGE        = "stage_change"
    OUTREACH_SENT       = "outreach_sent"
    REPLY_RECEIVED      = "reply_received"
    QUALIFICATION_DONE  = "qualification_done"
    ONBOARDING_STEP     = "onboarding_step"
    NUDGE_SENT          = "nudge_sent"
    POOL_CREATED        = "pool_created"
    OBJECTION_RAISED    = "objection_raised"


# ── Leads ─────────────────────────────────────────────────────────────────────

class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Identity
    project_name: Mapped[str]      = mapped_column(String(255), nullable=False)
    token_symbol: Mapped[str | None] = mapped_column(String(20))
    chain: Mapped[Chain]           = mapped_column(String(20), nullable=False)
    contract_address: Mapped[str | None] = mapped_column(String(100))
    website: Mapped[str | None]    = mapped_column(Text)

    # Contact links (Twitter, Telegram, Discord handles/links)
    contact_links: Mapped[dict]    = mapped_column(JSONB, default=dict)

    # Market data (snapshot at discovery)
    market_cap_usd: Mapped[float | None]  = mapped_column(Float)
    price_usd: Mapped[float | None]       = mapped_column(Float)
    volume_24h_usd: Mapped[float | None]  = mapped_column(Float)
    liquidity_usd: Mapped[float | None]   = mapped_column(Float)

    # Scoring
    score: Mapped[float]           = mapped_column(Float, default=0.0)
    priority: Mapped[LeadPriority] = mapped_column(String(10), default=LeadPriority.COLD)

    # Signals (raw extracted data)
    pain_signals: Mapped[list]     = mapped_column(JSONB, default=list)
    activity_metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    # e.g. {"tweet_freq_7d": 23, "telegram_members": 1200, "discord_members": 800}

    # Qualification output
    qualification_score: Mapped[float | None]  = mapped_column(Float)
    qualification_data: Mapped[dict]           = mapped_column(JSONB, default=dict)
    # e.g. {"objections": [...], "readiness_level": "high", "community_size": 1200}

    # Onboarding progress
    onboarding_step: Mapped[int]   = mapped_column(Integer, default=0)
    onboarding_data: Mapped[dict]  = mapped_column(JSONB, default=dict)

    # Lifecycle
    stage: Mapped[LeadStage]       = mapped_column(String(20), default=LeadStage.DISCOVERED)
    is_deleted: Mapped[bool]       = mapped_column(Boolean, default=False)

    # Discovery metadata
    source_platform: Mapped[str | None]  = mapped_column(String(50))
    source_url: Mapped[str | None]       = mapped_column(Text)
    first_seen_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity_at: Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Timestamps
    created_at: Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    events: Mapped[list["LeadEvent"]]           = relationship(back_populates="lead", cascade="all, delete-orphan")
    followups: Mapped[list["FollowUp"]]         = relationship(back_populates="lead", cascade="all, delete-orphan")
    memory: Mapped["LeadMemory | None"]         = relationship(back_populates="lead", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("contract_address", "chain", name="uq_lead_contract_chain"),
        Index("ix_lead_stage", "stage"),
        Index("ix_lead_priority", "priority"),
        Index("ix_lead_score", "score"),
        Index("ix_lead_chain", "chain"),
        Index("ix_lead_deleted", "is_deleted"),
    )

    def __repr__(self) -> str:
        return f"<Lead {self.project_name} [{self.stage}] score={self.score:.1f}>"


# ── Conversations ─────────────────────────────────────────────────────────────

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)

    channel: Mapped[OutreachChannel] = mapped_column(String(20), nullable=False)
    external_thread_id: Mapped[str | None] = mapped_column(String(255))  # DM thread ID, Telegram chat ID, etc.

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lead: Mapped["Lead"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

    __table_args__ = (
        Index("ix_conv_lead_id", "lead_id"),
        Index("ix_conv_channel", "channel"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)

    direction: Mapped[MessageDirection] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict)  # full API response stored
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    model_used: Mapped[str | None] = mapped_column(String(60))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_msg_conv_id", "conversation_id"),
        Index("ix_msg_direction", "direction"),
        Index("ix_msg_created_at", "created_at"),
    )


# ── Lead Events (audit trail) ─────────────────────────────────────────────────

class LeadEvent(Base):
    __tablename__ = "lead_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)

    event_type: Mapped[EventType]   = mapped_column(String(40), nullable=False)
    payload: Mapped[dict]           = mapped_column(JSONB, default=dict)
    # For stage changes: {"from": "discovered", "to": "contacted"}
    # For onboarding steps: {"step": 2, "step_name": "pool_config_explained"}

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lead: Mapped["Lead"] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_event_lead_id", "lead_id"),
        Index("ix_event_type", "event_type"),
        Index("ix_event_created_at", "created_at"),
    )


# ── Follow-Up Schedule ────────────────────────────────────────────────────────

class FollowUp(Base):
    __tablename__ = "followups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)

    channel: Mapped[OutreachChannel] = mapped_column(String(20), nullable=False)
    message_template: Mapped[str]    = mapped_column(Text, nullable=False)
    scheduled_at: Mapped[datetime]   = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_sent: Mapped[bool]            = mapped_column(Boolean, default=False)
    is_cancelled: Mapped[bool]       = mapped_column(Boolean, default=False)
    attempt_count: Mapped[int]       = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lead: Mapped["Lead"] = relationship(back_populates="followups")

    __table_args__ = (
        Index("ix_followup_lead_id", "lead_id"),
        Index("ix_followup_scheduled", "scheduled_at", "is_sent"),
    )


# ── Per-Project Memory (for Orchestrator context) ─────────────────────────────

class LeadMemory(Base):
    __tablename__ = "lead_memory"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Condensed conversation summary regenerated periodically
    summary: Mapped[str | None] = mapped_column(Text)
    # Key facts extracted: pain points, agreed terms, objections addressed
    key_facts: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Raw history for Claude context window (last N turns)
    recent_turns: Mapped[list] = mapped_column(JSONB, default=list)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    lead: Mapped["Lead"] = relationship(back_populates="memory")


# ── Knowledge Base Documents ──────────────────────────────────────────────────

class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str]          = mapped_column(String(500), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str]        = mapped_column(Text, nullable=False)
    content_hash: Mapped[str]   = mapped_column(String(64))  # SHA-256 for dedup
    is_indexed: Mapped[bool]    = mapped_column(Boolean, default=False)
    pinecone_ids: Mapped[list]  = mapped_column(JSONB, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_doc_hash"),
        Index("ix_doc_indexed", "is_indexed"),
    )


# ── System metrics / dashboard analytics ─────────────────────────────────────

class DailyMetrics(Base):
    __tablename__ = "daily_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date: Mapped[datetime]        = mapped_column(DateTime(timezone=True), nullable=False, unique=True)

    leads_discovered: Mapped[int] = mapped_column(Integer, default=0)
    leads_contacted: Mapped[int]  = mapped_column(Integer, default=0)
    leads_qualified: Mapped[int]  = mapped_column(Integer, default=0)
    leads_onboarding: Mapped[int] = mapped_column(Integer, default=0)
    leads_converted: Mapped[int]  = mapped_column(Integer, default=0)
    messages_sent: Mapped[int]    = mapped_column(Integer, default=0)
    replies_received: Mapped[int] = mapped_column(Integer, default=0)
    nudges_sent: Mapped[int]      = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
