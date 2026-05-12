"""
Module-level bot registry.
Avoids circular imports between main.py (which owns app.state)
and services that need to send Discord DMs.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.discord_hunter import DiscordHunter

_discord_bot: "DiscordHunter | None" = None


def register_bot(bot: "DiscordHunter") -> None:
    global _discord_bot
    _discord_bot = bot


def get_bot() -> "DiscordHunter | None":
    return _discord_bot
