"""
Hunter Service Orchestrator.

Runs on a schedule (every HUNTER_INTERVAL_SECONDS).
Pipeline per run:
  1. Scan onchain sources for tokens in 30k–3M range
  2. Cross-reference with Twitter/Telegram/Discord signals
  3. Score each candidate
  4. Deduplicate against existing DB leads
  5. Write new leads to DB
  6. Push high-priority leads to Outreach queue
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import (
    AgentLockKey, QueueName, RedisLock, enqueue,
    get_redis, is_agent_enabled,
)
from app.db.crud import upsert_lead, log_event
from app.db.session import AsyncSessionLocal
from app.models.lead import Chain, EventType, LeadPriority, LeadStage
from app.schemas.lead import LeadCreate, HunterLeadPayload
from app.services.onchain import OnchainAggregator, TokenSnapshot
from app.services.scorer import ScoreBreakdown, score_lead
from app.services.twitter_hunter import TwitterHunter, TwitterSignal
from app.services.telegram_hunter import TelegramHunter
from app.services.discord_hunter import DiscordProjectSignal

logger = logging.getLogger(__name__)


class HunterOrchestrator:
    def __init__(self):
        self.onchain   = OnchainAggregator()
        self.twitter   = TwitterHunter()
        self.telegram  = TelegramHunter()
        # Discord bot is started separately in app lifespan; passed in at runtime.
        self._discord_signals: list[DiscordProjectSignal] = []

    def ingest_discord_signal(self, sig: DiscordProjectSignal) -> None:
        """Called by the Discord bot's real-time on_message handler."""
        self._discord_signals.append(sig)

    # ── Main entry point ──────────────────────────────────────────────────────

    async def run(self) -> dict[str, int]:
        """
        Execute one full hunter run. Returns stats dict.
        Acquires a distributed lock to prevent concurrent runs.
        """
        redis = await get_redis()

        if not await is_agent_enabled(redis, "hunter"):
            logger.info("Hunter agent is disabled — skipping run")
            return {"skipped": 1}

        try:
            async with RedisLock(redis, AgentLockKey.HUNTER, ttl=600):
                return await self._execute()
        except RuntimeError:
            logger.warning("Hunter already running (lock held) — skipping")
            return {"skipped": 1}

    async def _execute(self) -> dict[str, int]:
        start = datetime.now(timezone.utc)
        stats = {
            "tokens_scanned": 0,
            "twitter_signals": 0,            "telegram_signals": 0,
            "discord_signals": 0,
            "leads_created": 0,
            "leads_updated": 0,
            "queued_for_outreach": 0,
        }

        logger.info("Hunter run starting")

        # ── Step 1: Onchain scan ──────────────────────────────────────────────
        try:
            token_snapshots = await self.onchain.scan_new_tokens()
            stats["tokens_scanned"] = len(token_snapshots)
            logger.info(f"Onchain: {len(token_snapshots)} tokens in range")
        except Exception as e:
            logger.error(f"Onchain scan failed: {e}")
            token_snapshots = []

        # ── Step 2: Social scans (parallel) ───────────────────────────────────
        twitter_task  = asyncio.create_task(self._safe_twitter())
        telegram_task = asyncio.create_task(self._safe_telegram())

        tw_signals, tg_signals = await asyncio.gather(
            twitter_task, telegram_task
        )
        stats["twitter_signals"]  = len(tw_signals)
        stats["telegram_signals"] = len(tg_signals)

        dc_signals = list(self._discord_signals)
        self._discord_signals.clear()
        stats["discord_signals"] = len(dc_signals)

        # ── Step 3: Build candidate payloads ──────────────────────────────────
        candidates = await self._build_candidates(
            token_snapshots, tw_signals, tg_signals, dc_signals
        )

        # ── Step 4: Write to DB, dispatch high-priority ───────────────────────
        async with AsyncSessionLocal() as db:
            for payload in candidates:
                try:
                    lead_create = LeadCreate(
                        project_name=payload.project_name,
                        chain=payload.chain,
                        token_symbol=payload.token_symbol,
                        contract_address=payload.contract_address,
                        contact_links=payload.contact_links,
                        market_cap_usd=payload.market_cap,
                        score=payload.score,
                        priority=payload.priority_level,
                        pain_signals=payload.pain_signals,
                        activity_metrics=payload.activity_metrics,
                        source_platform=payload.source_platform,
                        source_url=payload.source_url,
                    )
                    lead, created = await upsert_lead(db, lead_create)
                    await db.commit()

                    if created:
                        stats["leads_created"] += 1
                        await log_event(db, lead.id, EventType.STAGE_CHANGE, {
                            "from": None, "to": LeadStage.DISCOVERED,
                            "source": payload.source_platform,
                            "score": payload.score,
                        })
                        await db.commit()
                    else:
                        stats["leads_updated"] += 1

                    # Queue HOT and WARM leads for outreach
                    if payload.priority_level in (LeadPriority.HOT, LeadPriority.WARM):
                        redis = await get_redis()
                        await enqueue(redis, QueueName.OUTREACH_TASKS, {
                            "type": "initial_outreach",
                            "lead_id": str(lead.id),
                            "priority": payload.priority_level.value,
                        })
                        stats["queued_for_outreach"] += 1

                except Exception as e:
                    logger.error(f"Failed to persist lead {payload.project_name}: {e}")
                    await db.rollback()

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info(f"Hunter run complete in {elapsed:.1f}s | stats={stats}")
        return stats

    # ── Safe wrappers ─────────────────────────────────────────────────────────

    async def _safe_twitter(self) -> list[TwitterSignal]:
        try:
            return await self.twitter.hunt()
        except Exception as e:
            logger.error(f"Twitter hunt error: {e}")
            return []

    async def _safe_telegram(self):
        try:
            return await self.telegram.hunt()
        except Exception as e:
            logger.error(f"Telegram hunt error: {e}")
            return []

    # ── Candidate builder ─────────────────────────────────────────────────────

    async def _build_candidates(
        self,
        tokens: list[TokenSnapshot],
        tw_signals: list[TwitterSignal],
        tg_signals: list,
        dc_signals: list[DiscordProjectSignal],
    ) -> list[HunterLeadPayload]:
        """
        Merge signals from all sources into unique HunterLeadPayload objects.
        Deduplication key: (contract_address + chain) or (project_name normalized).
        """
        seen: dict[str, HunterLeadPayload] = {}

        # ── Onchain-first: we have hard market cap data ───────────────────────
        for token in tokens:
            key = f"{token.contract_address}:{token.chain.value}"

            # Try to find matching social signals by ticker
            tw_match = next(
                (s for s in tw_signals
                 if token.token_symbol.upper() in s.profile.description.upper()
                 or token.token_symbol.upper() in " ".join(s.sample_tweets).upper()),
                None,
            )

            pain_signals: list[str] = []
            contact_links: dict[str, str] = {"dexscreener": token.dex_url}
            twitter_followers = 0
            engagement_rate = 0.0
            last_activity: datetime | None = None
            tweet_freq = 0

            if tw_match:
                pain_signals.extend(tw_match.pain_signals)
                contact_links["twitter"] = tw_match.profile.profile_url
                twitter_followers = tw_match.profile.followers
                engagement_rate = tw_match.engagement_rate
                last_activity = tw_match.last_tweet_at
                tweet_freq = tw_match.tweet_frequency_7d

            pain_signals = list(set(pain_signals))

            # Holder count (async — fetch concurrently in batches for performance)
            holder_count = 0
            try:
                hc = await self.onchain.get_holder_count(token)
                holder_count = hc or 0
            except Exception:
                pass

            breakdown = score_lead(
                market_cap_usd=token.market_cap_usd,
                pain_signals=pain_signals,
                engagement_rate=engagement_rate,
                last_activity_at=last_activity,
                twitter_followers=twitter_followers,
                activity_metrics={"tweet_freq_7d": tweet_freq, "holder_count": holder_count},
            )

            payload = HunterLeadPayload(
                project_name=token.token_name or token.token_symbol,
                chain=token.chain,
                token_symbol=token.token_symbol,
                contract_address=token.contract_address,
                market_cap=token.market_cap_usd,
                contact_links=contact_links,
                score=breakdown.total,
                pain_signals=pain_signals,
                activity_metrics={
                    "tweet_freq_7d": tweet_freq,
                    "twitter_followers": twitter_followers,
                    "holder_count": holder_count,
                    "engagement_rate": engagement_rate,
                    "volume_24h": token.volume_24h_usd,
                    "score_breakdown": {
                        "market_cap": breakdown.market_cap_score,
                        "pain_signals": breakdown.pain_signal_score,
                        "engagement": breakdown.engagement_score,
                        "recency": breakdown.recency_score,
                        "community": breakdown.community_score,
                    },
                    "rationale": breakdown.rationale,
                },
                priority_level=breakdown.priority,
                source_platform="dexscreener",
                source_url=token.dex_url,
            )
            seen[key] = payload

        # ── Social-only signals: no onchain match yet ─────────────────────────
        for sig in tw_signals:
            # Only include if we didn't already pick them up from onchain
            handle = sig.profile.handle.lower().replace("@", "")
            key = f"twitter:{handle}"
            if key in seen:
                continue
            # Can't confirm market cap — skip unless strong pain signal
            if not sig.pain_signals:
                continue

            breakdown = score_lead(
                market_cap_usd=150_000,     # assume mid-range if no data
                pain_signals=sig.pain_signals,
                engagement_rate=sig.engagement_rate,
                last_activity_at=sig.last_tweet_at,
                twitter_followers=sig.profile.followers,
            )
            # Only include if they score warm or better
            if breakdown.total < settings.SCORE_WARM_THRESHOLD:
                continue

            payload = HunterLeadPayload(
                project_name=sig.profile.name,
                chain=Chain.ETHEREUM,   # unknown — default, confirm in qualification
                token_symbol=None,
                contract_address=None,
                market_cap=0.0,
                contact_links={"twitter": sig.profile.profile_url},
                score=breakdown.total,
                pain_signals=sig.pain_signals,
                activity_metrics={
                    "tweet_freq_7d": sig.tweet_frequency_7d,
                    "twitter_followers": sig.profile.followers,
                    "engagement_rate": sig.engagement_rate,
                    "rationale": breakdown.rationale,
                },
                priority_level=breakdown.priority,
                source_platform="twitter",
                source_url=sig.profile.profile_url,
            )
            seen[key] = payload

        logger.info(f"Built {len(seen)} unique lead candidates")
        return list(seen.values())

    async def close(self) -> None:
        await self.onchain.close()
        await self.telegram.close()


# ── Background scheduler ───────────────────────────────────────────────────────

async def run_hunter_loop(hunter: HunterOrchestrator) -> None:
    """
    Infinite loop that runs the hunter every HUNTER_INTERVAL_SECONDS.
    Designed to run as an asyncio background task from app lifespan.
    """
    while True:
        try:
            stats = await hunter.run()
            logger.info(f"Hunter loop stats: {stats}")
        except Exception as e:
            logger.error(f"Hunter loop error: {e}")
        await asyncio.sleep(settings.HUNTER_INTERVAL_SECONDS)
