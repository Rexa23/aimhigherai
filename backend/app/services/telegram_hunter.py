"""
Telegram Hunter.
Uses python-telegram-bot in polling mode to join/monitor public groups,
plus the Telegram Bot API to fetch chat info and message samples.

Strategy:
  1. Maintain a watchlist of Web3-relevant public Telegram groups/channels.
  2. On each run, fetch recent messages from each group via getUpdates or
     exportChatInviteLink flows.
  3. Parse project-signal keywords and pain signals in messages.
  4. Extract @username handles to cross-reference with Twitter profiles.

Note: Bot must be added as admin to groups it reads from.
For public channels, the bot can read via chat_id directly.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from telegram import Bot, Chat
from telegram.error import BadRequest, Forbidden, TelegramError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.services.twitter_hunter import _PAIN_RE

logger = logging.getLogger(__name__)

# ── Target group watchlist ─────────────────────────────────────────────────────
# These are public Web3 community groups where founders congregate.
# Extend this list as intelligence grows.

WATCHLIST_GROUPS: list[str] = [
    "@web3marketing",
    "@cryptolaunchpad",
    "@defi_founders",
    "@solana_projects",
    "@bnbchain_community",
    "@basechain_builders",
    "@nft_projects_hub",
    "@tokenlaunch_community",
    "@crypto_marketing_help",
    "@smallcap_gems",
]

# Keyword patterns that indicate a project is being discussed
PROJECT_SIGNAL_RE = re.compile(
    r"(token|launch|presale|fair launch|community|whitelist|airdrop|"
    r"marketing|dex|cmc|coingecko|listed|chart|holders|liquidity)",
    re.IGNORECASE,
)

# Extract possible token tickers ($TOKEN)
TICKER_RE = re.compile(r"\$([A-Z]{2,10})\b")


@dataclass
class TelegramGroupSnapshot:
    chat_id: str | int
    group_title: str
    member_count: int
    description: str
    username: str | None
    invite_link: str | None
    is_verified: bool
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class TelegramProjectSignal:
    group: TelegramGroupSnapshot
    mentioned_tickers: list[str]
    pain_signals: list[str]
    project_mentions: list[str]    # raw message excerpts
    contact_username: str | None   # @handle of the poster
    message_count_24h: int
    last_message_at: datetime | None


class TelegramHunter:
    def __init__(self):
        self._bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        self._rate_limit_delay = 0.5  # seconds between API calls

    async def _safe_get_chat(self, chat_id: str) -> Chat | None:
        await asyncio.sleep(self._rate_limit_delay)
        try:
            return await self._bot.get_chat(chat_id)
        except (BadRequest, Forbidden) as e:
            logger.debug(f"Cannot access chat {chat_id}: {e}")
            return None
        except TelegramError as e:
            logger.warning(f"Telegram error for {chat_id}: {e}")
            return None

    @retry(
        retry=retry_if_exception_type(TelegramError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def get_group_snapshot(self, chat_id: str) -> TelegramGroupSnapshot | None:
        chat = await self._safe_get_chat(chat_id)
        if not chat:
            return None

        member_count = 0
        try:
            member_count = await self._bot.get_chat_member_count(chat.id)
        except TelegramError:
            pass

        return TelegramGroupSnapshot(
            chat_id=chat.id,
            group_title=chat.title or "",
            member_count=member_count,
            description=chat.description or "",
            username=chat.username,
            invite_link=chat.invite_link,
            is_verified=bool(getattr(chat, "is_verified", False)),
            raw={
                "id": chat.id,
                "type": chat.type,
                "title": chat.title,
                "username": chat.username,
            },
        )

    def _parse_pain_signals(self, texts: list[str]) -> list[str]:
        signals = set()
        combined = " ".join(texts)
        for pattern in _PAIN_RE:
            match = pattern.search(combined)
            if match:
                start = max(0, match.start() - 10)
                end = min(len(combined), match.end() + 10)
                signals.add(combined[start:end].strip())
        return list(signals)

    def _extract_project_snippets(self, texts: list[str]) -> tuple[list[str], list[str]]:
        """Returns (project_mention_snippets, tickers)."""
        snippets = []
        tickers: set[str] = set()
        for text in texts:
            if PROJECT_SIGNAL_RE.search(text):
                snippets.append(text[:200])
            for m in TICKER_RE.finditer(text):
                tickers.add(m.group(1))
        return snippets[:10], list(tickers)

    async def scan_group(self, chat_id: str) -> TelegramProjectSignal | None:
        snapshot = await self.get_group_snapshot(chat_id)
        if not snapshot:
            return None

        # We can only read messages if the bot has been added to the group.
        # For groups where the bot isn't present, we only have metadata.
        # Message reading is done via webhook handler (see outreach service).
        # Here we return the metadata-only signal.
        return TelegramProjectSignal(
            group=snapshot,
            mentioned_tickers=[],
            pain_signals=[],
            project_mentions=[],
            contact_username=snapshot.username,
            message_count_24h=0,
            last_message_at=None,
        )

    async def process_incoming_message(
        self,
        chat_id: int,
        text: str,
        sender_username: str | None,
        sent_at: datetime,
    ) -> TelegramProjectSignal | None:
        """
        Called by the Telegram webhook when a message arrives in a monitored group.
        Returns a signal if the message contains project or pain indicators.
        """
        if not PROJECT_SIGNAL_RE.search(text) and not any(p.search(text) for p in _PAIN_RE):
            return None

        snapshot = await self.get_group_snapshot(str(chat_id))
        if not snapshot:
            return None

        snippets, tickers = self._extract_project_snippets([text])
        pain = self._parse_pain_signals([text])

        return TelegramProjectSignal(
            group=snapshot,
            mentioned_tickers=tickers,
            pain_signals=pain,
            project_mentions=snippets,
            contact_username=sender_username,
            message_count_24h=1,
            last_message_at=sent_at,
        )

    async def hunt(self) -> list[TelegramProjectSignal]:
        """
        Scan all watchlist groups for metadata signals.
        Deep message analysis happens via the real-time webhook.
        """
        signals: list[TelegramProjectSignal] = []
        for chat_id in WATCHLIST_GROUPS:
            sig = await self.scan_group(chat_id)
            if sig and sig.group.member_count >= 100:
                signals.append(sig)
            await asyncio.sleep(0.3)  # gentle rate limiting

        logger.info(f"Telegram hunt: {len(signals)} groups scanned")
        return signals

    async def send_message(self, chat_id: int | str, text: str) -> bool:
        """Send a direct message. Used by the Outreach Service."""
        try:
            await self._bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            return True
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
            return False

    async def close(self) -> None:
        await self._bot.close()
