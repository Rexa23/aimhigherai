"""
Outreach Worker.
Consumes tasks from OUTREACH_TASKS queue and executes them:
  - initial_outreach: send first message to a new lead
  - reply: respond to an inbound message
  - followup: send a scheduled follow-up

Each task fetches lead context, generates message via Claude,
dispatches to the appropriate platform bot, and records everything.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import (
    QueueName, ScheduleKey, dequeue, enqueue,
    get_redis, is_agent_enabled, move_to_dead_letter, schedule_task,
)
from app.db.crud import (
    add_message, get_lead, get_conversation_messages,
    get_or_create_conversation, log_event, transition_stage, update_lead_memory,
)
from app.db.session import AsyncSessionLocal
from app.models.lead import EventType, LeadStage, MessageDirection, OutreachChannel
from app.schemas.lead import LeadUpdate
from app.services.outreach_composer import (
    generate_first_message, generate_followup, generate_reply,
)
from app.services.twitter_hunter import TwitterHunter
from app.services.telegram_hunter import TelegramHunter

logger = logging.getLogger(__name__)

# Maximum follow-up attempts before marking a lead as dead
MAX_FOLLOWUP_ATTEMPTS = 4
FOLLOWUP_INTERVALS_DAYS = [2, 4, 7, 14]  # days after each attempt


class OutreachWorker:
    def __init__(
        self,
        twitter: TwitterHunter | None = None,
        telegram: TelegramHunter | None = None,
    ):
        self._twitter  = twitter or TwitterHunter()
        self._telegram = telegram or TelegramHunter()

    # ── Main run loop ─────────────────────────────────────────────────────────

    async def run_forever(self) -> None:
        """Blocking worker loop. Run as a background asyncio task."""
        logger.info("Outreach worker started")
        while True:
            try:
                redis = await get_redis()
                if not await is_agent_enabled(redis, "outreach"):
                    await asyncio.sleep(10)
                    continue

                task = await dequeue(redis, QueueName.OUTREACH_TASKS, timeout=5)
                if task is None:
                    continue

                await self._dispatch(task)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Outreach worker top-level error: {e}")
                await asyncio.sleep(5)

    # ── Task dispatcher ───────────────────────────────────────────────────────

    async def _dispatch(self, task: dict[str, Any]) -> None:
        task_type = task.get("type", "initial_outreach")
        try:
            if task_type == "initial_outreach":
                await self._handle_initial_outreach(task)
            elif task_type == "reply":
                await self._handle_reply(task)
            elif task_type == "followup":
                await self._handle_followup(task)
            else:
                logger.warning(f"Unknown outreach task type: {task_type}")
        except Exception as e:
            logger.error(f"Outreach task failed [{task_type}]: {e}")
            redis = await get_redis()
            await move_to_dead_letter(redis, QueueName.OUTREACH_TASKS, task, str(e))

    # ── Initial outreach ──────────────────────────────────────────────────────

    async def _handle_initial_outreach(self, task: dict[str, Any]) -> None:
        lead_id = uuid.UUID(task["lead_id"])

        async with AsyncSessionLocal() as db:
            lead = await get_lead(db, lead_id)
            if not lead:
                logger.warning(f"Lead {lead_id} not found for initial outreach")
                return
            if lead.stage not in (LeadStage.DISCOVERED, LeadStage.CONTACTED):
                return  # already progressed

            memory = lead.memory
            memory_summary = memory.summary if memory else None
            key_facts      = memory.key_facts if memory else {}

            # Determine best channel from contact_links
            channel = self._pick_channel(lead.contact_links)
            if not channel:
                logger.info(f"No contact channel for {lead.project_name} — skipping")
                return

            lead_data = {
                "project_name": lead.project_name,
                "chain":        lead.chain,
                "market_cap_usd": lead.market_cap_usd,
                "score":        lead.score,
                "priority":     lead.priority,
                "pain_signals": lead.pain_signals,
                "stage":        lead.stage,
            }

            message = await generate_first_message(
                lead=lead_data,
                channel=channel.value,
                memory_summary=memory_summary,
                key_facts=key_facts,
            )

            # Send via appropriate platform
            sent = await self._send(channel, lead.contact_links, message)
            if not sent:
                logger.warning(f"Failed to send initial outreach to {lead.project_name}")
                return

            # Persist conversation + message
            conv, _ = await get_or_create_conversation(db, lead_id, channel)
            await add_message(
                db,
                conversation_id=conv.id,
                direction=MessageDirection.OUTBOUND,
                content=message,
                ai_generated=True,
                model_used=settings.GEMINI_MODEL,
            )

            # Transition stage
            if lead.stage == LeadStage.DISCOVERED:
                await transition_stage(db, lead, LeadStage.CONTACTED, "initial outreach sent")

            await log_event(db, lead_id, EventType.OUTREACH_SENT, {
                "channel": channel.value, "message_length": len(message),
            })

            # Schedule first follow-up
            await self._schedule_followup(db, lead_id, channel, attempt=1)

            await db.commit()
            logger.info(f"Initial outreach sent to {lead.project_name} via {channel.value}")

    # ── Reply handler ─────────────────────────────────────────────────────────

    async def _handle_reply(self, task: dict[str, Any]) -> None:
        lead_id         = uuid.UUID(task["lead_id"])
        conversation_id = uuid.UUID(task["conversation_id"])
        channel         = task.get("channel", "twitter")
        inbound_msg     = task.get("inbound_message", "")

        async with AsyncSessionLocal() as db:
            lead = await get_lead(db, lead_id)
            if not lead:
                return

            memory     = lead.memory
            key_facts  = memory.key_facts if memory else {}
            recent_turns = memory.recent_turns if memory else []

            lead_data = {
                "project_name":  lead.project_name,
                "chain":         lead.chain,
                "market_cap_usd": lead.market_cap_usd,
                "score":         lead.score,
                "priority":      lead.priority,
                "pain_signals":  lead.pain_signals,
                "stage":         lead.stage,
            }

            # Fetch recent conversation history
            msgs = await get_conversation_messages(db, conversation_id, limit=20)
            history = [
                {"role": "user" if m.direction == MessageDirection.INBOUND else "assistant",
                 "content": m.content}
                for m in msgs
            ]

            reply = await generate_reply(
                lead=lead_data,
                conversation_history=history,
                inbound_message=inbound_msg,
                channel=channel,
                memory_summary=memory.summary if memory else None,
                key_facts=key_facts,
            )

            # Conversion engine / qualification agent may supply a pre-generated
            # message (e.g. objection response). Use it directly if present.
            if task.get("override_content"):
                reply = task["override_content"]

            channel_enum = OutreachChannel(channel)
            sent = await self._send(channel_enum, lead.contact_links, reply)
            if not sent:
                return

            await add_message(
                db,
                conversation_id=conversation_id,
                direction=MessageDirection.OUTBOUND,
                content=reply,
                ai_generated=True,
                model_used=settings.GEMINI_MODEL,
            )

            # Update memory: append turn, periodically regenerate summary
            new_turns = recent_turns + [
                {"role": "user",      "content": inbound_msg},
                {"role": "assistant", "content": reply},
            ]
            await update_lead_memory(db, lead_id, recent_turns=new_turns)

            # Trigger qualification if enough conversation turns
            if len(new_turns) >= 4 and lead.stage == LeadStage.CONTACTED:
                redis = await get_redis()
                await enqueue(redis, QueueName.QUALIFY_TASKS, {
                    "lead_id": str(lead_id),
                    "conversation_id": str(conversation_id),
                })

            await db.commit()
            logger.info(f"Reply sent to {lead.project_name} ({len(reply)} chars)")

    # ── Follow-up handler ─────────────────────────────────────────────────────

    async def _handle_followup(self, task: dict[str, Any]) -> None:
        lead_id    = uuid.UUID(task["lead_id"])
        attempt    = task.get("attempt", 1)
        channel_str = task.get("channel", "twitter")

        if attempt > MAX_FOLLOWUP_ATTEMPTS:
            async with AsyncSessionLocal() as db:
                lead = await get_lead(db, lead_id)
                if lead and lead.stage == LeadStage.CONTACTED:
                    await transition_stage(db, lead, LeadStage.DEAD, "max follow-ups exhausted")
                    await db.commit()
            return

        async with AsyncSessionLocal() as db:
            lead = await get_lead(db, lead_id)
            if not lead:
                return
            if lead.stage not in (LeadStage.DISCOVERED, LeadStage.CONTACTED):
                return  # replied and progressed — don't follow up

            days = FOLLOWUP_INTERVALS_DAYS[min(attempt - 1, len(FOLLOWUP_INTERVALS_DAYS) - 1)]
            channel = OutreachChannel(channel_str)

            lead_data = {
                "project_name": lead.project_name,
                "chain":        lead.chain,
                "pain_signals": lead.pain_signals,
                "stage":        lead.stage,
            }
            memory_summary = lead.memory.summary if lead.memory else None

            message = await generate_followup(
                lead=lead_data,
                days_since_contact=days,
                attempt_number=attempt,
                channel=channel.value,
                memory_summary=memory_summary,
            )

            sent = await self._send(channel, lead.contact_links, message)
            if not sent:
                return

            conv, _ = await get_or_create_conversation(db, lead_id, channel)
            await add_message(
                db,
                conversation_id=conv.id,
                direction=MessageDirection.OUTBOUND,
                content=message,
                ai_generated=True,
                model_used=settings.GEMINI_MODEL,
            )

            await log_event(db, lead_id, EventType.NUDGE_SENT, {
                "attempt": attempt, "channel": channel.value,
            })

            # Schedule next follow-up
            await self._schedule_followup(db, lead_id, channel, attempt=attempt + 1)
            await db.commit()
            logger.info(f"Follow-up #{attempt} sent to {lead.project_name}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _pick_channel(self, contact_links: dict[str, str]) -> OutreachChannel | None:
        preference = [OutreachChannel.TELEGRAM, OutreachChannel.TWITTER, OutreachChannel.DISCORD]
        for ch in preference:
            if ch.value in contact_links and contact_links[ch.value]:
                return ch
        return None

    async def _send(
        self,
        channel: OutreachChannel,
        contact_links: dict[str, str],
        message: str,
    ) -> bool:
        try:
            if channel == OutreachChannel.TWITTER:
                return await self._send_twitter(contact_links.get("twitter", ""), message)
            elif channel == OutreachChannel.TELEGRAM:
                return await self._send_telegram(contact_links.get("telegram", ""), message)
            elif channel == OutreachChannel.DISCORD:
                return await self._send_discord(contact_links.get("discord", ""), message)
            return False
        except Exception as e:
            logger.error(f"Send error on {channel.value}: {e}")
            return False

    async def _send_twitter(self, profile_url: str, message: str) -> bool:
        """Send Twitter DM. Requires knowing the user_id from the profile URL."""
        try:
            # Extract handle from URL and resolve to user_id via API
            handle = profile_url.rstrip("/").split("/")[-1].lstrip("@")
            response = await self._twitter._client.get_user(username=handle, user_auth=True)
            if not response.data:
                logger.warning(f"Could not resolve Twitter user: {handle}")
                return False
            user_id = response.data.id
            await self._twitter._client.create_direct_message(
                participant_id=user_id, text=message
            )
            return True
        except Exception as e:
            logger.warning(f"Twitter DM failed to {profile_url}: {e}")
            return False

    async def _send_telegram(self, contact: str, message: str) -> bool:
        """Send Telegram message. contact can be a chat_id or @username."""
        return await self._telegram.send_message(contact, message)

    async def _send_discord(self, discord_handle: str, message: str) -> bool:
        """
        Discord DM requires the user_id integer.
        contact_links["discord"] = "user:{user_id}" format.
        Fetches bot from a module-level registry to avoid circular imports.
        """
        from app.services import discord_registry
        discord_bot = discord_registry.get_bot()
        if not discord_bot:
            logger.warning("Discord bot not registered — DM skipped")
            return False
        try:
            user_id = int(discord_handle.replace("user:", ""))
            return await discord_bot.send_dm(user_id, message)
        except (ValueError, Exception) as e:
            logger.warning(f"Discord DM failed: {e}")
            return False

    async def _schedule_followup(
        self,
        db: AsyncSession,
        lead_id: uuid.UUID,
        channel: OutreachChannel,
        attempt: int,
    ) -> None:
        if attempt > MAX_FOLLOWUP_ATTEMPTS:
            return
        days = FOLLOWUP_INTERVALS_DAYS[min(attempt - 1, len(FOLLOWUP_INTERVALS_DAYS) - 1)]
        run_at = datetime.now(timezone.utc) + timedelta(days=days)

        redis = await get_redis()
        await schedule_task(redis, ScheduleKey.FOLLOWUPS, {
            "type":    "followup",
            "lead_id": str(lead_id),
            "channel": channel.value,
            "attempt": attempt,
        }, run_at=run_at)
