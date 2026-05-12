"""
Outreach message composer.
Generates personalized first-contact messages and dynamic reply continuations
using Claude. Tone: direct, confident, human — no AI phrases.
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.gemini_client import complete, build_conversation_messages, format_lead_context

logger = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────

OUTREACH_SYSTEM = """You are a sharp, confident BD rep for AimHigher — a Web3 marketing platform where crypto communities run real engagement campaigns directly on the platform. Projects open pools, community members complete tasks, everyone wins.

Your job: start conversations that convert. You reach out to small Web3 projects (30k–3M market cap) who are struggling with marketing or need more visibility.

TONE RULES — follow these absolutely:
- Write like a real person texting or DMing. Short sentences. Get to the point.
- No corporate language. No "I hope this finds you well." No "synergies."
- No AI phrases: never say "I'd be happy to", "certainly", "of course", "as an AI".
- Sound like someone who actually knows crypto — use the lingo naturally.
- Be direct about why you're reaching out. Vague openers get ignored.
- Max 3 sentences for a cold opener. Max 5 sentences for a reply.
- Never pitch the full platform in the first message. Open a conversation.
- If there's a pain signal, lead with acknowledging it — show you understand their problem first.

AIMHIGHER VALUE PROPS (use selectively, not all at once):
- Community-driven campaigns: real people complete tasks, not bots
- Projects only pay for actual engagement — no wasted ad spend  
- Works on Ethereum, BNB, Solana, Base
- Much cheaper than KOLs or paid promo — better ROI
- Campaign can go live in under 24 hours
- Built-in community = instant exposure to engaged Web3 users

WHAT TO NEVER SAY:
- "I came across your project" (too generic)
- "I'd love to connect" (corporate)
- "Would you be open to a quick call" (too salesy too early)
- Long paragraphs
- Multiple questions in one message
"""


# ── First contact ─────────────────────────────────────────────────────────────

async def generate_first_message(
    lead: dict[str, Any],
    channel: str,
    memory_summary: str | None = None,
    key_facts: dict[str, Any] | None = None,
) -> str:
    """
    Generate a personalized first outreach message.
    Adapts tone and length based on channel (Twitter DM vs Telegram vs Discord).
    """
    pain_signals = lead.get("pain_signals", [])
    project_name = lead.get("project_name", "your project")
    market_cap   = lead.get("market_cap_usd") or 0
    chain        = lead.get("chain", "")

    # Build pain context
    pain_context = ""
    if pain_signals:
        pain_context = f"\nDetected pain signals from their posts: {'; '.join(pain_signals[:2])}"

    # Channel-specific length instruction
    channel_note = {
        "twitter":  "This is a Twitter/X DM. Max 240 characters.",
        "telegram": "This is a Telegram DM. 2–3 short sentences.",
        "discord":  "This is a Discord DM. Casual, 2–3 sentences.",
    }.get(channel, "Keep it under 3 sentences.")

    user_prompt = f"""Write a cold outreach DM for this project:

{format_lead_context({**lead, 'memory_summary': memory_summary, 'key_facts': key_facts or {}})}
{pain_context}

Channel context: {channel_note}

Instructions:
- If there's a pain signal, acknowledge the specific problem first.
- Do NOT pitch AimHigher directly — just open the door.
- Ask exactly one question or make one observation that invites a reply.
- Sound like you genuinely looked at their project, not a blast template.
- Do not start with "Hey" or "Hi" — vary the opener.
"""

    message = await complete(
        system=OUTREACH_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=300,
        temperature=0.85,   # slightly higher for variety
    )

    logger.info(f"Generated first message for {project_name} via {channel} ({len(message)} chars)")
    return message.strip()


# ── Dynamic reply generator ───────────────────────────────────────────────────

async def generate_reply(
    lead: dict[str, Any],
    conversation_history: list[dict[str, str]],
    inbound_message: str,
    channel: str,
    memory_summary: str | None = None,
    key_facts: dict[str, Any] | None = None,
) -> str:
    """
    Generate a contextual reply to an inbound message.
    Injects full lead context and conversation history.
    """
    lead_ctx = format_lead_context({**lead, 'memory_summary': memory_summary, 'key_facts': key_facts or {}})

    system = OUTREACH_SYSTEM + f"""

CURRENT LEAD CONTEXT:
{lead_ctx}

CURRENT STAGE: {lead.get('stage', 'contacted')}
CHANNEL: {channel}

Conversation history is provided. The most recent message from them is the last user turn.
Your response should feel like a natural continuation of the conversation.
If they show interest: move toward explaining AimHigher's value.
If they push back or object: acknowledge first, then reframe.
If they ask a question: answer it concisely then redirect to their marketing pain.
"""

    messages = build_conversation_messages(
        history=conversation_history,
        new_user_message=inbound_message,
        max_turns=16,
    )

    reply = await complete(
        system=system,
        messages=messages,
        max_tokens=400,
        temperature=0.75,
    )

    logger.info(f"Generated reply for {lead.get('project_name')} ({len(reply)} chars)")
    return reply.strip()


# ── Follow-up message generator ───────────────────────────────────────────────

async def generate_followup(
    lead: dict[str, Any],
    days_since_contact: int,
    attempt_number: int,
    channel: str,
    memory_summary: str | None = None,
) -> str:
    """
    Generate a follow-up message for an unresponsive lead.
    Each attempt takes a different angle to avoid feeling spammy.
    """
    angles = [
        "Reference a specific market signal or trend relevant to their chain.",
        "Lead with a concrete result or metric from another project on AimHigher.",
        "Be very brief — 1 sentence max. Just checking if they got the first message.",
        "Ask a binary yes/no question about their current marketing situation.",
    ]
    angle = angles[min(attempt_number - 1, len(angles) - 1)]

    lead_ctx = format_lead_context({**lead, 'memory_summary': memory_summary})

    user_prompt = f"""Write a follow-up message. This is attempt #{attempt_number}, sent {days_since_contact} day(s) after the first contact.

Lead context:
{lead_ctx}

Approach for this attempt: {angle}

Rules:
- Do NOT reference that this is a follow-up ("just following up", "circling back" — banned).
- Make it feel like a fresh, relevant touch — not a chase.
- Max 2 sentences.
- Channel: {channel}
"""

    message = await complete(
        system=OUTREACH_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=200,
        temperature=0.9,
    )

    logger.info(f"Generated follow-up #{attempt_number} for {lead.get('project_name')}")
    return message.strip()


# ── AI suggestion generator (for human agents reviewing in dashboard) ─────────

async def generate_suggestions(
    lead: dict[str, Any],
    conversation_history: list[dict[str, str]],
    last_inbound: str,
) -> list[str]:
    """
    Generate 3 reply suggestions shown in the dashboard's AI panel.
    Human agents can pick one or write their own.
    """
    lead_ctx = format_lead_context(lead)
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in conversation_history[-6:]
    )

    user_prompt = f"""Generate exactly 3 different reply options for this message: "{last_inbound}"

Lead context: {lead_ctx}

Recent conversation:
{history_text}

Format: Return a JSON array of 3 strings. Each string is a complete reply option.
Vary the approach:
  Option 1: Direct and confident — push toward AimHigher
  Option 2: Empathetic — acknowledge their pain first
  Option 3: Low-pressure — ask a question, no pitch

JSON array only, no other text."""

    from app.services.gemini_client import complete_json
    result = await complete_json(
        system=OUTREACH_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=600,
    )

    if isinstance(result, list):
        return [str(s) for s in result[:3]]

    # Fallback if Claude returns {"suggestions": [...]}
    if isinstance(result, dict):
        for key in ("suggestions", "options", "replies"):
            if key in result and isinstance(result[key], list):
                return [str(s) for s in result[key][:3]]

    return []
