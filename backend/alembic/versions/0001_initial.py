"""create all tables

Revision ID: 0001_initial
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── leads ─────────────────────────────────────────────────────────────
    op.create_table(
        "leads",
        sa.Column("id",               postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_name",     sa.String(255), nullable=False),
        sa.Column("token_symbol",     sa.String(20)),
        sa.Column("chain",            sa.String(20), nullable=False),
        sa.Column("contract_address", sa.String(100)),
        sa.Column("website",          sa.Text()),
        sa.Column("contact_links",    postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("market_cap_usd",   sa.Float()),
        sa.Column("price_usd",        sa.Float()),
        sa.Column("volume_24h_usd",   sa.Float()),
        sa.Column("liquidity_usd",    sa.Float()),
        sa.Column("score",            sa.Float(), nullable=False, server_default="0"),
        sa.Column("priority",         sa.String(10), nullable=False, server_default="cold"),
        sa.Column("pain_signals",     postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("activity_metrics", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("qualification_score", sa.Float()),
        sa.Column("qualification_data",  postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("onboarding_step",  sa.Integer(), nullable=False, server_default="0"),
        sa.Column("onboarding_data",  postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("stage",            sa.String(20), nullable=False, server_default="discovered"),
        sa.Column("is_deleted",       sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("source_platform",  sa.String(50)),
        sa.Column("source_url",       sa.Text()),
        sa.Column("first_seen_at",    sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("converted_at",     sa.DateTime(timezone=True)),
        sa.Column("created_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("contract_address", "chain", name="uq_lead_contract_chain"),
    )
    op.create_index("ix_lead_stage",    "leads", ["stage"])
    op.create_index("ix_lead_priority", "leads", ["priority"])
    op.create_index("ix_lead_score",    "leads", ["score"])
    op.create_index("ix_lead_chain",    "leads", ["chain"])
    op.create_index("ix_lead_deleted",  "leads", ["is_deleted"])

    # ── conversations ─────────────────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id",                 postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id",            postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel",            sa.String(20), nullable=False),
        sa.Column("external_thread_id", sa.String(255)),
        sa.Column("is_active",          sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at",         sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_message_at",    sa.DateTime(timezone=True)),
    )
    op.create_index("ix_conv_lead_id", "conversations", ["lead_id"])
    op.create_index("ix_conv_channel",  "conversations", ["channel"])

    # ── messages ──────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id",              postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction",       sa.String(10), nullable=False),
        sa.Column("content",         sa.Text(), nullable=False),
        sa.Column("raw_payload",     postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("ai_generated",    sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("model_used",      sa.String(60)),
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_msg_conv_id",    "messages", ["conversation_id"])
    op.create_index("ix_msg_direction",  "messages", ["direction"])
    op.create_index("ix_msg_created_at", "messages", ["created_at"])

    # ── lead_events ───────────────────────────────────────────────────────
    op.create_table(
        "lead_events",
        sa.Column("id",         postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id",    postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("payload",    postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_event_lead_id",    "lead_events", ["lead_id"])
    op.create_index("ix_event_type",       "lead_events", ["event_type"])
    op.create_index("ix_event_created_at", "lead_events", ["created_at"])

    # ── followups ─────────────────────────────────────────────────────────
    op.create_table(
        "followups",
        sa.Column("id",               postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id",          postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel",          sa.String(20), nullable=False),
        sa.Column("message_template", sa.Text(), nullable=False),
        sa.Column("scheduled_at",     sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at",          sa.DateTime(timezone=True)),
        sa.Column("is_sent",          sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_cancelled",     sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("attempt_count",    sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_followup_lead_id",  "followups", ["lead_id"])
    op.create_index("ix_followup_scheduled","followups", ["scheduled_at", "is_sent"])

    # ── lead_memory ───────────────────────────────────────────────────────
    op.create_table(
        "lead_memory",
        sa.Column("id",           postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id",      postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("summary",      sa.Text()),
        sa.Column("key_facts",    postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("recent_turns", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("updated_at",   sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── knowledge_docs ────────────────────────────────────────────────────
    op.create_table(
        "knowledge_docs",
        sa.Column("id",           postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title",        sa.String(500), nullable=False),
        sa.Column("source_url",   sa.Text()),
        sa.Column("content",      sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("is_indexed",   sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("pinecone_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at",   sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("indexed_at",   sa.DateTime(timezone=True)),
        sa.UniqueConstraint("content_hash", name="uq_doc_hash"),
    )
    op.create_index("ix_doc_indexed", "knowledge_docs", ["is_indexed"])

    # ── daily_metrics ─────────────────────────────────────────────────────
    op.create_table(
        "daily_metrics",
        sa.Column("id",               postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("date",             sa.DateTime(timezone=True), nullable=False, unique=True),
        sa.Column("leads_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leads_contacted",  sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leads_qualified",  sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leads_onboarding", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leads_converted",  sa.Integer(), nullable=False, server_default="0"),
        sa.Column("messages_sent",    sa.Integer(), nullable=False, server_default="0"),
        sa.Column("replies_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("nudges_sent",      sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("daily_metrics")
    op.drop_table("knowledge_docs")
    op.drop_table("lead_memory")
    op.drop_table("followups")
    op.drop_table("lead_events")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("leads")
