"""
Google Gemini (Generative AI) client wrapper.
Provides async-friendly functions: complete, complete_json, stream_complete,
and helper builders used across agents.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, AsyncIterator, List

import google.generativeai as genai
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configure client at import-time using environment-stored key
genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
_model = None


def _get_model():
    global _model
    if _model is None:
        # Create a model instance wrapper
        _model = genai.GenerativeModel(settings.GEMINI_MODEL)
    return _model


# ── Prompt helpers ───────────────────────────────────────────────────────────

def build_conversation_messages(
    history: List[dict[str, str]],
    new_user_message: str,
    max_turns: int = 20,
) -> List[dict[str, Any]]:
    """
    Convert stored message history (list of {role, content}) into a
    simple alternating message list and append the new user message.
    """
    trimmed = history[-max_turns:]
    cleaned: List[dict[str, Any]] = []
    for msg in trimmed:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if cleaned and cleaned[-1]["role"] == role:
            cleaned[-1]["content"] = content
        else:
            cleaned.append({"role": role, "content": content})

    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)

    cleaned.append({"role": "user", "content": new_user_message})
    return cleaned


def format_lead_context(lead_data: dict[str, Any]) -> str:
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


# ── Core completion ──────────────────────────────────────────────────────────

@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=20),
)
async def complete(
    system: str,
    messages: List[dict[str, Any]],
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> str:
    """
    Generate a plain-text completion using Gemini.
    """
    prompt_parts = [system]
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        prompt_parts.append(f"{role.upper()}: {content}")
    prompt = "\n".join(prompt_parts)

    def _sync_call():
        model = _get_model()
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        )
        resp = model.generate_content(
            prompt,
            generation_config=generation_config,
        )
        try:
            return resp.text
        except Exception:
            try:
                return resp.candidates[0].content.parts[0].text
            except Exception:
                return str(resp)
    text = await asyncio.to_thread(_sync_call)
    return text


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def complete_json(
    system: str,
    messages: List[dict[str, Any]],
    max_tokens: int = 1024,
) -> dict[str, Any]:
    json_system = (
        system
        + "\n\nRespond ONLY with a valid JSON object. No explanation, no markdown fences."
    )
    raw = await complete(json_system, messages, max_tokens=max_tokens, temperature=0.2)

    # strip possible fences
    raw = raw.strip()
    if raw.startswith("```"):
        # remove fencing
        raw = raw.strip('`')
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Gemini JSON parse error: {e}\nRaw: {raw[:300]}")
        raise ValueError(f"Gemini returned invalid JSON: {e}") from e


async def stream_complete(
    system: str,
    messages: List[dict[str, Any]],
    max_tokens: int = 1024,
) -> AsyncIterator[str]:
    """Yield full response as a single chunk (Gemini streaming not used).
    This preserves the async iterator interface used by the dashboard.
    """
    text = await complete(system, messages, max_tokens=max_tokens)
    yield text