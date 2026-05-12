"""
Anthropic Claude API client.
Central wrapper used by Outreach, Qualification, and Onboarding agents.
Handles context window management, retries, and streaming.
"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator

import anthropic
from tenacity import (
    retry, retry_if_exception_type,
    stop_after_attempt, wait_exponential,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def get_claude() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


# ── Core completion ────────────────────────────────────────────────────────────

@retry(
    retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.InternalServerError)),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=5, max=60),
)
async def complete(
    system: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> str:
    client = get_claude()
    response = await client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=messages,
    )
    return response.content[0].text


@retry(
    retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.InternalServerError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=5, max=30),
)
async def complete_json(
    system: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """
    Request a JSON-only response. Appends a reminder to the system prompt
    and strips any accidental markdown fences before parsing.
    """
    import json, re

    json_system = (
        system
        + "\n\nRespond ONLY with a valid JSON object. "
          "No explanation, no markdown fences, no preamble."
    )
    raw = await complete(json_system, messages, max_tokens=max_tokens, temperature=0.2)

    # Strip ```json ... ``` if Claude adds it anyway
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Claude JSON parse error: {e}\nRaw: {raw[:300]}")
        raise ValueError(f"Claude returned invalid JSON: {e}") from e


async def stream_complete(
    system: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 1024,
) -> AsyncIterator[str]:
    """Yield text chunks for streaming responses to the dashboard."""
    client = get_claude()
    async with client.messages.stream(
        model=settings.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text


# ── Context builder helpers ───────────────────────────────────────────────────

def build_conversation_messages(
    history: list[dict[str, str]],
    new_user_message: str,
    max_turns: int = 20,
) -> list[dict[str, Any]]:
    """
    Convert stored message history (list of {role, content}) into
    the Anthropic messages format, capped at max_turns.
    Ensures the sequence alternates user/assistant correctly.
    """
    # Take the last max_turns messages
    trimmed = history[-max_turns:]

    # Anthropic requires messages to alternate user/assistant, starting with user.
    # Filter out consecutive same-role messages (keep most recent).
    cleaned: list[dict[str, Any]] = []
    for msg in trimmed:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if cleaned and cleaned[-1]["role"] == role:
            cleaned[-1]["content"] = content  # overwrite with newer
        else:
            cleaned.append({"role": role, "content": content})

    # Ensure sequence starts with user
    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)

    cleaned.append({"role": "user", "content": new_user_message})
    return cleaned


def format_lead_context(lead_data: dict[str, Any]) -> str:
    """Render lead facts as a structured context block for system prompts."""
    lines = [
        f"Project: {lead_data.get('project_name', 'Unknown')}",
        f"Chain: {lead_data.get('chain', 'Unknown')}",
        f"Market Cap: ${lead_data.get('market_cap_usd', 0):,.0f}" if lead_data.get('market_cap_usd') else "Market Cap: Unknown",
        f"Score: {lead_data.get('score', 0):.1f}/100",
        f"Priority: {lead_data.get('priority', 'cold').upper()}",
    ]
    if lead_data.get("pain_signals"):
        lines.append("Pain signals detected:")
        for sig in lead_data["pain_signals"][:3]:
            lines.append(f"  • {sig}")
    if lead_data.get("memory_summary"):
        lines.append(f"\nConversation summary: {lead_data['memory_summary']}")
    if lead_data.get("key_facts"):
        lines.append("Known facts:")
        for k, v in list(lead_data["key_facts"].items())[:5]:
            lines.append(f"  • {k}: {v}")
    return "\n".join(lines)
