"""
Orchestrator.
Central nervous system of the AimHigher AI Onboarding Team.

Responsibilities:
  1. Route leads between agents based on lifecycle stage
  2. Enforce valid stage transitions
  3. Maintain per-project memory (periodic summarisation)
  4. Broadcast real-time state changes to the dashboard
  5. Detect anomalies: leads stuck, duplicate outreach, queue overflow
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.core.redis import (
    QueueName, enqueue, get_redis, is_agent_enabled,
)
from app.db.crud import get_lead, update_lead_memory, log_event
from app.db.session import AsyncSessionLocal
from app.models.lead import EventType, Lead, LeadStage
from app.services.gemini_client import complete

logger = logging.getLogger(__name__)

MEMORY_SUMMARISE_EVERY_N_TURNS = 10   # regenerate summary every 10 new turns


# ── Memory summariser ──────────────────────────────────────────────────────────

async def summarise_conversation(
    project_name: str,
    recent_turns: list[dict[str, str]],
    existing_summary: str | None,
) -> str:
    """
    Condense conversation history into a 2–4 sentence summary for injection
    into future prompts without consuming the full context window.
    """
    turns_text = "\n".join(
        f"{t['role'].upper()}: {t['content']}" for t in recent_turns[-20:]
    )
    prev = f"\nExisting summary: {existing_summary}" if existing_summary else ""

    prompt = f"""Summarise this conversation for {project_name} in 2–4 sentences.
Capture: current relationship status, key facts revealed, objections raised,
what was agreed, and where we are in the onboarding process.{prev}

Conversation:
{turns_text}

Write a concise factual summary. No labels or headers."""

    return await complete(
        system="You are a concise CRM note writer for a Web3 marketing platform.",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.3,
    )


# ── Stage router ──────────────────────────────────────────────────────────────

STAGE_QUEUE_MAP: dict[LeadStage, QueueName] = {
    LeadStage.DISCOVERED:    QueueName.OUTREACH_TASKS,
    LeadStage.CONTACTED:     QueueName.QUALIFY_TASKS,
    LeadStage.QUALIFIED:     QueueName.ONBOARDING_TASKS,
    LeadStage.ONBOARDING:    QueueName.CONVERSION_TASKS,
}


async def route_lead(lead_id: uuid.UUID) -> bool:
    """
    Read current lead stage and enqueue to the correct downstream agent.
    Returns True if successfully routed.
    """
    async with AsyncSessionLocal() as db:
        lead = await get_lead(db, lead_id)
        if not lead:
            logger.warning(f"Orchestrator: lead {lead_id} not found")
            return False

        target_queue = STAGE_QUEUE_MAP.get(lead.stage)
        if not target_queue:
            return False   # CONVERTED, DISQUALIFIED, DEAD — no routing needed

        redis = await get_redis()
        payload: dict[str, Any] = {"lead_id": str(lead_id)}

        if lead.stage == LeadStage.DISCOVERED:
            payload["type"] = "initial_outreach"
        elif lead.stage == LeadStage.CONTACTED:
            payload["type"] = "qualify"
        elif lead.stage == LeadStage.QUALIFIED:
            payload["type"] = "start_onboarding"
        elif lead.stage == LeadStage.ONBOARDING:
            payload["type"] = "check_inactivity"

        await enqueue(redis, target_queue, payload)
        logger.info(f"Orchestrator routed {lead.project_name} [{lead.stage}] → {target_queue.value}")
        return True


# ── Orchestrator background worker ────────────────────────────────────────────

class Orchestrator:
    """
    Runs periodic maintenance tasks:
    - Memory summarisation for leads with many conversation turns
    - Anomaly detection: stuck leads, queue overflow
    - Daily metric snapshots
    """

    async def run_forever(self) -> None:
        logger.info("Orchestrator started")
        while True:
            try:
                await asyncio.sleep(300)   # run every 5 minutes
                await self._maintain_memory()
                await self._detect_anomalies()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Orchestrator error: {e}")

    # ── Memory maintenance ────────────────────────────────────────────────────

    async def _maintain_memory(self) -> None:
        """
        For any lead whose recent_turns count is a multiple of
        MEMORY_SUMMARISE_EVERY_N_TURNS, regenerate the summary.
        """
        async with AsyncSessionLocal() as db:
            from app.models.lead import LeadMemory
            result = await db.execute(
                select(Lead, LeadMemory)
                .join(LeadMemory, Lead.id == LeadMemory.lead_id)
                .where(
                    Lead.stage.in_([LeadStage.CONTACTED, LeadStage.QUALIFIED, LeadStage.ONBOARDING]),
                    Lead.is_deleted == False,
                )
            )
            rows = result.all()

        for lead, memory in rows:
            turns = memory.recent_turns or []
            if len(turns) < MEMORY_SUMMARISE_EVERY_N_TURNS:
                continue
            # Only re-summarise if turn count grew since last check
            marker_key = f"memory_summarised_at_{lead.id}"
            redis = await get_redis()
            last_count = await redis.get(marker_key)
            if last_count and int(last_count) == len(turns):
                continue  # nothing new

            try:
                summary = await summarise_conversation(
                    project_name=lead.project_name,
                    recent_turns=turns,
                    existing_summary=memory.summary,
                )
                async with AsyncSessionLocal() as db:
                    await update_lead_memory(db, lead.id, summary=summary)
                    await db.commit()
                await redis.set(marker_key, len(turns), ex=86400)
                logger.debug(f"Memory summarised for {lead.project_name}")
            except Exception as e:
                logger.warning(f"Memory summarisation failed for {lead.project_name}: {e}")

    # ── Anomaly detection ─────────────────────────────────────────────────────

    async def _detect_anomalies(self) -> None:
        """
        Flag leads that appear stuck:
        - In CONTACTED for > 5 days with no qualification
        - In QUALIFIED for > 2 days without starting onboarding
        - In ONBOARDING for > 14 days without converting
        """
        now = datetime.now(timezone.utc)
        thresholds = {
            LeadStage.CONTACTED:  timedelta(days=5),
            LeadStage.QUALIFIED:  timedelta(days=2),
            LeadStage.ONBOARDING: timedelta(days=14),
        }

        async with AsyncSessionLocal() as db:
            for stage, threshold in thresholds.items():
                cutoff = now - threshold
                result = await db.execute(
                    select(Lead).where(
                        Lead.stage == stage,
                        Lead.is_deleted == False,
                        Lead.last_activity_at < cutoff,
                    )
                )
                stuck_leads = result.scalars().all()

                for lead in stuck_leads:
                    age_days = (now - lead.last_activity_at.replace(tzinfo=timezone.utc)).days
                    logger.warning(
                        f"ANOMALY: {lead.project_name} stuck in {stage} for {age_days}d"
                    )
                    # Queue a nudge via conversion engine
                    redis = await get_redis()
                    await enqueue(redis, QueueName.CONVERSION_TASKS, {
                        "type":           "send_nudge",
                        "lead_id":        str(lead.id),
                        "nudge_type":     "stuck_step",
                        "hours_inactive": age_days * 24,
                    })

    # ── Queue health check ────────────────────────────────────────────────────

    @staticmethod
    async def get_queue_depths() -> dict[str, int]:
        redis = await get_redis()
        return {q.value: await redis.llen(q.value) for q in QueueName}
