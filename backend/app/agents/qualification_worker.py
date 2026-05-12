"""
Qualification Worker.
Consumes from QUALIFY_TASKS queue.
For each task:
  1. Load lead + full conversation history
  2. Run qualification extractor
  3. Persist result to lead record
  4. Transition stage: contacted → qualified (or disqualified)
  5. Dispatch qualified leads to ONBOARDING_TASKS
  6. Generate and queue objection-handling reply if objections found
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from app.core.redis import (
    QueueName, dequeue, enqueue, get_redis,
    is_agent_enabled, move_to_dead_letter,
)
from app.db.crud import (
    get_lead_with_conversations, log_event, transition_stage,
    update_lead_memory,
)
from app.db.session import AsyncSessionLocal
from app.models.lead import EventType, LeadPriority, LeadStage, MessageDirection
from app.schemas.lead import LeadUpdate
from app.agents.qualification import extract_qualification, generate_objection_response

logger = logging.getLogger(__name__)


class QualificationWorker:

    async def run_forever(self) -> None:
        logger.info("Qualification worker started")
        while True:
            try:
                redis = await get_redis()
                if not await is_agent_enabled(redis, "qualification"):
                    await asyncio.sleep(10)
                    continue

                task = await dequeue(redis, QueueName.QUALIFY_TASKS, timeout=5)
                if task is None:
                    continue

                await self._process(task)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Qualification worker error: {e}")
                await asyncio.sleep(5)

    async def _process(self, task: dict[str, Any]) -> None:
        lead_id = uuid.UUID(task["lead_id"])

        try:
            async with AsyncSessionLocal() as db:
                lead = await get_lead_with_conversations(db, lead_id)
                if not lead:
                    logger.warning(f"Lead {lead_id} not found for qualification")
                    return

                # Already past qualification — skip
                if lead.stage not in (LeadStage.CONTACTED, LeadStage.DISCOVERED):
                    return

                # Build flat conversation history across all channels
                history = self._flatten_conversations(lead.conversations)

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

                # ── Run extractor ─────────────────────────────────────────────
                result = await extract_qualification(lead_data, history)

                score    = result["qualification_score"]
                category = result["category"]
                readiness = result["readiness_level"]
                objections = result["objections"]
                extracted  = result["extracted_data"]

                logger.info(
                    f"Qualified {lead.project_name}: "
                    f"score={score} category={category} readiness={readiness}"
                )

                # ── Persist to lead ───────────────────────────────────────────
                lead.qualification_score = score
                lead.qualification_data  = {
                    "category":        category,
                    "readiness_level": readiness,
                    "objections":      objections,
                    **extracted,
                }

                # Update priority from qualification result
                priority_map = {
                    "hot":  LeadPriority.HOT,
                    "warm": LeadPriority.WARM,
                    "cold": LeadPriority.COLD,
                }
                lead.priority = priority_map.get(category, lead.priority)

                # Update confirmed market cap if extracted
                if extracted.get("confirmed_market_cap"):
                    lead.market_cap_usd = float(extracted["confirmed_market_cap"])

                # Update memory key_facts
                facts_update = {
                    k: v for k, v in extracted.items()
                    if v is not None and k in (
                        "confirmed_market_cap", "community_size_estimate",
                        "platforms", "decision_maker", "competitor_mentioned",
                        "budget_signal",
                    )
                }
                await update_lead_memory(db, lead_id, key_facts=facts_update)

                # ── Stage transition ──────────────────────────────────────────
                if category == "cold" and readiness == "low":
                    await transition_stage(
                        db, lead, LeadStage.DISQUALIFIED,
                        f"Qualification score {score:.0f} — cold/low readiness"
                    )
                else:
                    await transition_stage(
                        db, lead, LeadStage.QUALIFIED,
                        f"Qualification score {score:.0f} — {category}/{readiness}"
                    )

                await log_event(db, lead_id, EventType.QUALIFICATION_DONE, {
                    "score":         score,
                    "category":      category,
                    "readiness":     readiness,
                    "objection_count": len(objections),
                })

                await db.commit()

                # ── Dispatch to onboarding if qualified ───────────────────────
                redis = await get_redis()
                if lead.stage == LeadStage.QUALIFIED:
                    await enqueue(redis, QueueName.ONBOARDING_TASKS, {
                        "type":    "start_onboarding",
                        "lead_id": str(lead_id),
                    })
                    logger.info(f"Dispatched {lead.project_name} to onboarding")

                # ── Handle objections: queue a response ───────────────────────
                if objections and lead.stage == LeadStage.QUALIFIED:
                    top_objection = objections[0]
                    try:
                        objection_reply = await generate_objection_response(
                            top_objection, lead_data, history
                        )
                        # Enqueue as outreach reply task
                        active_conv = next(
                            (c for c in lead.conversations if c.is_active), None
                        )
                        if active_conv:
                            await enqueue(redis, QueueName.OUTREACH_TASKS, {
                                "type":             "reply",
                                "lead_id":          str(lead_id),
                                "conversation_id":  str(active_conv.id),
                                "channel":          active_conv.channel,
                                "inbound_message":  f"[objection] {top_objection}",
                                "override_content": objection_reply,
                            })
                    except Exception as e:
                        logger.warning(f"Objection response generation failed: {e}")

        except Exception as e:
            logger.error(f"Qualification failed for {lead_id}: {e}")
            redis = await get_redis()
            await move_to_dead_letter(redis, QueueName.QUALIFY_TASKS, task, str(e))

    @staticmethod
    def _flatten_conversations(conversations: list) -> list[dict[str, str]]:
        """Merge all conversation messages into a single chronological history."""
        all_msgs = []
        for conv in conversations:
            for msg in conv.messages:
                all_msgs.append({
                    "role": "user" if msg.direction == MessageDirection.INBOUND else "assistant",
                    "content": msg.content,
                    "created_at": msg.created_at,
                })
        all_msgs.sort(key=lambda m: m["created_at"])
        return [{"role": m["role"], "content": m["content"]} for m in all_msgs]
