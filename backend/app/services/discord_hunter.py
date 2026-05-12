"""
Discord Hunter.
Uses discord.py to:
  1. Monitor joined servers for project activity and pain signals.
  2. Parse messages from Web3-relevant channels.
  3. Track server growth signals (member counts, activity).

The bot must be invited to servers manually or via OAuth2 link.
Public Discord servers with the bot present are scanned on each hunter run.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import discord
from discord.ext import commands
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.services.twitter_hunter import _PAIN_RE, TICKER_RE

logger = logging.getLogger(__name__)

# ── Channel name filters — only read channels likely to contain project discussion

RELEVANT_CHANNEL_PATTERNS = re.compile(
    r"(general|announcement|marketing|shill|project|launch|dev|build|"
    r"community|discussion|lounge|main|chat|intro|welcome)",
    re.IGNORECASE,
)

PROJECT_KEYWORD_RE = re.compile(
    r"(token|launch|presale|airdrop|whitelist|marketing|holders|"
    r"liquidity|dex|cmc|coingecko|mcap|community growth)",
    re.IGNORECASE,
)

# Indicators that a server is a project's own server (not just a community hub)
OWN_PROJECT_RE = re.compile(
    r"(our token|our project|we built|we launched|team update|"
    r"roadmap|tokenomics|whitepaper|contract address|ca:|0x[a-fA-F0-9]{40})",
    re.IGNORECASE,
)


@dataclass
class DiscordServerSnapshot:
    guild_id: int
    guild_name: str
    member_count: int
    description: str | None
    icon_url: str | None
    vanity_url: str | None
    created_at: datetime
    boost_level: int
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiscordProjectSignal:
    server: DiscordServerSnapshot
    channel_name: str
    pain_signals: list[str]
    mentioned_tickers: list[str]
    sample_messages: list[str]
    is_own_project_server: bool
    contact_handle: str | None      # Discord username of likely project rep
    message_count_24h: int
    member_count: int
    last_activity_at: datetime | None


class DiscordHunter(commands.Bot):
    """
    Discord bot that doubles as a hunter.
    On startup, scans all joined guilds for project signals.
    Responds to incoming messages via on_message for real-time detection.
    """

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)
        self._signals: list[DiscordProjectSignal] = []
        self._signal_callbacks: list[Any] = []
        self._scanning = False

    def add_signal_callback(self, cb: Any) -> None:
        """Register a callback invoked when a new signal is detected."""
        self._signal_callbacks.append(cb)

    async def on_ready(self) -> None:
        logger.info(f"Discord bot ready: {self.user} | Guilds: {len(self.guilds)}")

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if not message.guild:
            return

        text = message.content
        if not (PROJECT_KEYWORD_RE.search(text) or any(p.search(text) for p in _PAIN_RE)):
            return

        signal = await self._build_signal_from_message(message)
        if signal:
            self._signals.append(signal)
            for cb in self._signal_callbacks:
                try:
                    await cb(signal)
                except Exception as e:
                    logger.error(f"Signal callback error: {e}")

    async def _build_signal_from_message(
        self, message: discord.Message
    ) -> DiscordProjectSignal | None:
        guild = message.guild
        if not guild:
            return None

        text = message.content
        pain = self._extract_pain_signals(text)
        tickers = list({m.group(1) for m in TICKER_RE.finditer(text)})
        is_own_project = bool(OWN_PROJECT_RE.search(text))

        server = DiscordServerSnapshot(
            guild_id=guild.id,
            guild_name=guild.name,
            member_count=guild.member_count or 0,
            description=guild.description,
            icon_url=str(guild.icon.url) if guild.icon else None,
            vanity_url=guild.vanity_url_code,
            created_at=guild.created_at,
            boost_level=guild.premium_tier,
            raw={"id": guild.id, "name": guild.name},
        )

        contact = str(message.author)

        return DiscordProjectSignal(
            server=server,
            channel_name=message.channel.name if hasattr(message.channel, "name") else "",
            pain_signals=pain,
            mentioned_tickers=tickers,
            sample_messages=[text[:300]],
            is_own_project_server=is_own_project,
            contact_handle=contact,
            message_count_24h=1,
            member_count=guild.member_count or 0,
            last_activity_at=message.created_at,
        )

    def _extract_pain_signals(self, text: str) -> list[str]:
        signals = set()
        for pattern in _PAIN_RE:
            match = pattern.search(text)
            if match:
                start = max(0, match.start() - 10)
                end = min(len(text), match.end() + 10)
                signals.add(text[start:end].strip())
        return list(signals)

    async def scan_all_guilds(self) -> list[DiscordProjectSignal]:
        """
        Proactive scan: iterate over all joined guilds and read recent messages
        from relevant channels. Called on hunter runs.
        """
        if self._scanning:
            return []
        self._scanning = True
        results: list[DiscordProjectSignal] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        for guild in self.guilds:
            try:
                guild_signals = await self._scan_guild(guild, since=cutoff)
                results.extend(guild_signals)
            except discord.Forbidden:
                logger.debug(f"No permission to read from guild: {guild.name}")
            except Exception as e:
                logger.warning(f"Guild scan error {guild.name}: {e}")

        self._scanning = False
        logger.info(f"Discord scan complete: {len(results)} signals from {len(self.guilds)} guilds")
        return results

    async def _scan_guild(
        self, guild: discord.Guild, since: datetime
    ) -> list[DiscordProjectSignal]:
        signals: list[DiscordProjectSignal] = []
        seen_channels = 0

        for channel in guild.text_channels:
            if not RELEVANT_CHANNEL_PATTERNS.search(channel.name):
                continue
            if seen_channels >= 3:  # max 3 channels per guild to stay within rate limits
                break
            seen_channels += 1

            messages: list[str] = []
            last_at: datetime | None = None
            try:
                async for msg in channel.history(after=since, limit=100):
                    if msg.author.bot:
                        continue
                    messages.append(msg.content)
                    if last_at is None or msg.created_at > last_at:
                        last_at = msg.created_at
                    await asyncio.sleep(0)  # yield to event loop
            except discord.Forbidden:
                continue
            except discord.HTTPException as e:
                logger.debug(f"HTTP error reading {channel.name}: {e}")
                continue

            if not messages:
                continue

            combined = " ".join(messages)
            pain = self._extract_pain_signals(combined)
            tickers = list({m.group(1) for m in TICKER_RE.finditer(combined)})
            is_own = bool(OWN_PROJECT_RE.search(combined))

            if not pain and not is_own and not tickers:
                continue

            server = DiscordServerSnapshot(
                guild_id=guild.id,
                guild_name=guild.name,
                member_count=guild.member_count or 0,
                description=guild.description,
                icon_url=str(guild.icon.url) if guild.icon else None,
                vanity_url=guild.vanity_url_code,
                created_at=guild.created_at,
                boost_level=guild.premium_tier,
            )

            signals.append(DiscordProjectSignal(
                server=server,
                channel_name=channel.name,
                pain_signals=pain,
                mentioned_tickers=tickers,
                sample_messages=messages[:5],
                is_own_project_server=is_own,
                contact_handle=None,
                message_count_24h=len(messages),
                member_count=guild.member_count or 0,
                last_activity_at=last_at,
            ))

        return signals

    async def send_dm(self, user_id: int, message: str) -> bool:
        """Send a DM to a Discord user. Used by the Outreach Service."""
        try:
            user = await self.fetch_user(user_id)
            await user.send(message)
            return True
        except (discord.Forbidden, discord.NotFound) as e:
            logger.warning(f"Cannot DM user {user_id}: {e}")
            return False
        except discord.HTTPException as e:
            logger.error(f"Discord DM failed: {e}")
            return False

    async def start_bot(self) -> None:
        """Non-blocking bot start for use within FastAPI lifespan."""
        asyncio.create_task(self.start(settings.DISCORD_BOT_TOKEN))
        # Wait for bot to be ready
        for _ in range(30):
            if self.is_ready():
                return
            await asyncio.sleep(1)
        logger.warning("Discord bot did not become ready within 30s")
