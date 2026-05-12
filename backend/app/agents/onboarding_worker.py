"""
Onboarding Worker.
Consumes ONBOARDING_TASKS queue.
Task types:
  - start_onboarding:  initialize onboarding for a qualified lead
  - onboarding_reply:  process an inbound message from a lead in onboarding
  - index_doc:         trigger vector indexing for a new knowledge doc
  - advance_step:      force-advance a stalled lead to the next step
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
from app.core.config import settings
from app.db.crud import (
    add_message, get_lead, get_lead_with_conversations, get_or_create_conversation,
    log_event, transition_stage, update_lead_memory,
)
from app.db.session import AsyncSessionLocal
from app.models.lead import EventType, LeadStage, MessageDirection, OutreachChannel
from app.agents.onboarding import (
    generate_onboarding_response, generate_step_intro, MAX_STEP,
)

logger = logging.getLogger(__name__)


class OnboardingWorker:

    async def run_forever(self) -> None:
        logger.info("Onboarding worker started")
        while True:
            try:
                redis = await get_redis()
                if not await is_agent_enabled(redis, "onboarding"):
                    await asyncio.sleep(10)
                    continue

                task = await dequeue(redis, QueueName.ONBOARDING_TASKS, timeout=5)
                if task is None:
                    continue

                task_type = task.get("type", "onboarding_reply")
                if task_type == "start_onboarding":
                    await self._start_onboarding(task)
                elif task_type == "onboarding_reply":
                    await self._handle_reply(task)
                elif task_type == "index_doc":
                    await self._index_doc(task)
                elif task_type == "advance_step":
                    await self._advance_step(task)
                else:
                    logger.warning(f"Unknown onboarding task type: {task_type}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Onboarding worker error: {e}")
                await asyncio.sleep(5)

    # ── Start onboarding ──────────────────────────────────────────────────────

    async def _start_onboarding(self, task: dict[str, Any]) -> None:
        lead_id = uuid.UUID(task["lead_id"])

        async with AsyncSessionLocal() as db:
            lead = await get_lead(db, lead_id)
            if not lead:
                return
            if lead.stage not in (LeadStage.QUALIFIED,):
                return

            await transition_stage(db, lead, LeadStage.ONBOARDING, "qualification passed")
            lead.onboarding_step = 0

            lead_data = self._lead_to_dict(lead)
            intro = await generate_step_intro(lead_data, step=0)

            # Send intro via active conversation channel
            channel = self._pick_channel(lead.conversations)
            if channel:
                conv, _ = await get_or_create_conversation(db, lead_id, channel)
                await add_message(
                    db,
                    conversation_id=conv.id,
                    direction=MessageDirection.OUTBOUND,
                    content=intro,
                    ai_generated=True,
                    model_used=settings.GEMINI_MODEL,
                )

            await log_event(db, lead_id, EventType.ONBOARDING_STEP, {
                "step": 0, "step_name": "introduction", "action": "started",
            })
            await db.commit()
            logger.info(f"Onboarding started for {lead.project_name}")

    # ── Handle inbound reply during onboarding ────────────────────────────────

    async def _handle_reply(self, task: dict[str, Any]) -> None:
        lead_id         = uuid.UUID(task["lead_id"])
        conversation_id = uuid.UUID(task["conversation_id"])
        user_message    = task.get("user_message", "")

        async with AsyncSessionLocal() as db:
            lead = await get_lead_with_conversations(db, lead_id)
            if not lead or lead.stage != LeadStage.ONBOARDING:
                return

            from app.agents.qualification_worker import QualificationWorker
            history = QualificationWorker._flatten_conversations(lead.conversations)

            lead_data    = self._lead_to_dict(lead)
            current_step = lead.onboarding_step or 0

            result = await generate_onboarding_response(
                lead=lead_data,
                conversation_history=history,
                user_message=user_message,
                current_step=current_step,
            )

            # Send reply
            await add_message(
                db,
                conversation_id=conversation_id,
                direction=MessageDirection.OUTBOUND,
                content=result["reply"],
                ai_generated=True,
                model_used=settings.GEMINI_MODEL,
            )

            # Advance step if complete
            if result["step_complete"]:
                new_step = result["next_step"]
                lead.onboarding_step = new_step
                await log_event(db, lead_id, EventType.ONBOARDING_STEP, {
                    "from_step": current_step,
                    "to_step":   new_step,
                    "sources":   result["sources_used"],
                })

                # Send step intro for next step (non-blocking)
                if new_step <= MAX_STEP:
                    intro = await generate_step_intro(lead_data, step=new_step)
                    await add_message(
                        db,
                        conversation_id=conversation_id,
                        direction=MessageDirection.OUTBOUND,
                        content=intro,
                        ai_generated=True,
                        model_used=settings.GEMINI_MODEL,
                    )

            # Update memory
            memory = lead.memory
            recent = list(memory.recent_turns if memory else [])
            recent += [
                {"role": "user",      "content": user_message},
                {"role": "assistant", "content": result["reply"]},
            ]
            await update_lead_memory(db, lead_id, recent_turns=recent)

            # Handle conversion signal
            if result.get("next_action") == "converted":
                await transition_stage(db, lead, LeadStage.CONVERTED, "pool created")
                redis = await get_redis()
                await enqueue(redis, QueueName.CONVERSION_TASKS, {
                    "type":    "pool_created",
                    "lead_id": str(lead_id),
                })

            await db.commit()

    # ── Index document ────────────────────────────────────────────────────────

    async def _index_doc(self, task: dict[str, Any]) -> None:
        doc_id = task.get("doc_id")
        if not doc_id:
            return
        try:
            from app.services.vector_store import run_indexing_job
            await run_indexing_job(doc_id)
        except Exception as e:
            logger.error(f"Doc indexing failed for {doc_id}: {e}")
            redis = await get_redis()
            await move_to_dead_letter(redis, QueueName.ONBOARDING_TASKS, task, str(e))

    # ── Force-advance step ────────────────────────────────────────────────────

    async def _advance_step(self, task: dict[str, Any]) -> None:
        lead_id = uuid.UUID(task["lead_id"])
        async with AsyncSessionLocal() as db:
            lead = await get_lead(db, lead_id)
            if not lead or lead.stage != LeadStage.ONBOARDING:
                return
            current = lead.onboarding_step or 0
            if current >= MAX_STEP:
                return
            new_step = current + 1
            lead.onboarding_step = new_step
            await log_event(db, lead_id, EventType.ONBOARDING_STEP, {
                "from_step": current, "to_step": new_step, "action": "force_advanced",
            })
            await db.commit()
            logger.info(f"Force-advanced {lead.project_name} step {current}→{new_step}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _lead_to_dict(lead) -> dict[str, Any]:
        return {
            "project_name":    lead.project_name,
            "chain":           lead.chain,
            "market_cap_usd":  lead.market_cap_usd,
            "score":           lead.score,
            "priority":        lead.priority,
            "pain_signals":    lead.pain_signals,
            "stage":           lead.stage,
            "onboarding_step": lead.onboarding_step,
            "qualification_data": lead.qualification_data,
            "memory_summary":  lead.memory.summary if lead.memory else None,
            "key_facts":       lead.memory.key_facts if lead.memory else {},
        }

    @staticmethod
    def _pick_channel(conversations: list) -> OutreachChannel | None:
        if not conversations:
            return None
        active = [c for c in conversations if c.is_active]
        if active:
            return active[0].channel
        return conversations[0].channel if conversations else None
