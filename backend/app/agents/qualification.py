"""
Qualification Agent — signal extractor.
Reads conversation history and lead metadata to produce a structured
qualification result: score, category, objections, readiness level.
Uses Claude with JSON output mode for deterministic extraction.
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.gemini_client import complete_json, complete, format_lead_context

logger = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────

QUALIFICATION_SYSTEM = """You are a qualification analyst for AimHigher — a Web3 marketing platform.
Your job is to read a conversation between our BD rep and a Web3 project team,
then extract structured intelligence about whether this project is ready to open
a campaign pool on AimHigher.

AimHigher context:
- Projects open "pools" with a budget. Community members complete tasks to earn rewards.
- Works on Ethereum, BNB Chain, Solana, Base.
- Target projects: 30k–3M market cap, active or semi-active community.
- Main value prop: real community engagement, not bot traffic or paid influencers.

Qualification criteria:
1. Market cap confirmed in 30k–3M range
2. Has an active community (Telegram, Discord, Twitter)
3. Expressed growth intent (wants more holders, volume, visibility)
4. Has a marketing pain point (wasted budget, low engagement, no traction)
5. Has decision-making authority (founder, CMO, or core team)
6. Is open to the platform (not dismissive, not locked into a competitor)

Readiness levels:
- high:   Meets 5–6 criteria, engaged in conversation, asked follow-up questions
- medium: Meets 3–4 criteria, interested but cautious
- low:    Meets 1–2 criteria, vague or non-committal

Common objections to detect:
- "too expensive" / "don't have budget"
- "we already use [competitor]" (e.g. Zealy, Galxe, QuestN, Layer3)
- "not sure if it works" / "need proof"
- "need to discuss with team"
- "our community is not active enough"
- "we're not ready yet"
- "rug suspicion" / trust concerns about AimHigher
"""

# ── Extractor ─────────────────────────────────────────────────────────────────

async def extract_qualification(
    lead: dict[str, Any],
    conversation_history: list[dict[str, str]],
) -> dict[str, Any]:
    """
    Returns a structured qualification dict:
    {
      qualification_score: float (0-100),
      category: "hot" | "warm" | "cold",
      objections: list[str],
      readiness_level: "high" | "medium" | "low",
      extracted_data: {
        confirmed_market_cap: float | null,
        community_size_estimate: int | null,
        platforms: list[str],
        decision_maker: bool | null,
        growth_intent: bool,
        pain_confirmed: bool,
        competitor_mentioned: str | null,
        budget_signal: str | null,   // "has budget" | "tight budget" | "no budget" | "unknown"
      }
    }
    """
    lead_ctx = format_lead_context(lead)
    convo_text = _format_conversation(conversation_history)

    user_prompt = f"""Analyse this lead and conversation. Extract a qualification result.

LEAD DATA:
{lead_ctx}

CONVERSATION:
{convo_text}

Return a JSON object with EXACTLY this structure:
{{
  "qualification_score": <float 0-100>,
  "category": "<hot|warm|cold>",
  "objections": [<string>, ...],
  "readiness_level": "<high|medium|low>",
  "extracted_data": {{
    "confirmed_market_cap": <float or null>,
    "community_size_estimate": <int or null>,
    "platforms": [<string>, ...],
    "decision_maker": <true|false|null>,
    "growth_intent": <true|false>,
    "pain_confirmed": <true|false>,
    "competitor_mentioned": <string or null>,
    "budget_signal": "<has budget|tight budget|no budget|unknown>"
  }}
}}

Scoring guide:
- Start at 0. Add points for each confirmed criterion (max ~17 pts each across 6 criteria).
- Deduct 10–20 pts for strong objections (no budget, locked competitor, distrust).
- Bonus 5 pts if they asked a question about AimHigher unprompted.
- Bonus 5 pts if decision maker is confirmed.
- Cap at 100. Floor at 0.

category thresholds: hot >= 70, warm >= 40, cold < 40.
"""

    result = await complete_json(
        system=QUALIFICATION_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=800,
    )

    # Validate and sanitise
    return _validate_result(result, lead)


def _format_conversation(history: list[dict[str, str]]) -> str:
    if not history:
        return "(No conversation yet — qualify from lead metadata only)"
    lines = []
    for msg in history[-30:]:  # last 30 turns max
        role = "BD REP" if msg.get("role") == "assistant" else "LEAD"
        content = msg.get("content", "").strip()
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _validate_result(raw: dict[str, Any], lead: dict[str, Any]) -> dict[str, Any]:
    """Ensure all required fields exist with sane defaults."""
    score = float(raw.get("qualification_score", 0))
    score = max(0.0, min(100.0, score))

    category = raw.get("category", "cold")
    if category not in ("hot", "warm", "cold"):
        category = "hot" if score >= 70 else "warm" if score >= 40 else "cold"

    readiness = raw.get("readiness_level", "low")
    if readiness not in ("high", "medium", "low"):
        readiness = "low"

    objections = raw.get("objections", [])
    if not isinstance(objections, list):
        objections = []

    extracted = raw.get("extracted_data", {})
    if not isinstance(extracted, dict):
        extracted = {}

    extracted.setdefault("confirmed_market_cap", lead.get("market_cap_usd"))
    extracted.setdefault("community_size_estimate", None)
    extracted.setdefault("platforms", [])
    extracted.setdefault("decision_maker", None)
    extracted.setdefault("growth_intent", bool(lead.get("pain_signals")))
    extracted.setdefault("pain_confirmed", bool(lead.get("pain_signals")))
    extracted.setdefault("competitor_mentioned", None)
    extracted.setdefault("budget_signal", "unknown")

    return {
        "qualification_score": round(score, 2),
        "category":            category,
        "objections":          [str(o) for o in objections[:8]],
        "readiness_level":     readiness,
        "extracted_data":      extracted,
    }


# ── Objection handler ─────────────────────────────────────────────────────────

OBJECTION_RESPONSES = {
    "too expensive": """Acknowledge the concern, then reframe around ROI.
AimHigher charges per completed task — you never pay for impressions or bots.
Many projects spend less than they would on one KOL post and get 10x the engagement.
Ask: what did their last marketing spend produce?""",

    "already use competitor": """Don't attack the competitor directly.
Ask what they like about it and what's missing.
Position AimHigher as complementary or a better fit for on-chain task campaigns.
Zealy/Galxe are points-based — AimHigher pays in actual tokens, which drives real holder buy-in.""",

    "need proof": """Offer specifics: project names they can verify on-chain, tx counts,
wallet growth numbers. Suggest a small pilot pool (minimum budget) to test before committing.""",

    "not ready yet": """Ask what 'ready' looks like for them and what timeline they're working toward.
Offer to stay in touch and check back at a specific date.
Plant a seed: the earlier they build community, the easier launch will be.""",

    "trust concerns": """Be transparent. AimHigher is non-custodial — projects keep their tokens
until tasks are verified. Smart contract audits are public. Community can verify everything on-chain.""",
}


async def generate_objection_response(
    objection: str,
    lead: dict[str, Any],
    conversation_history: list[dict[str, str]],
) -> str:
    """
    Generate a specific objection-handling response tailored to this lead.
    Uses the objection playbook as context for Claude.
    """
    # Find closest playbook entry
    playbook_entry = ""
    objection_lower = objection.lower()
    for key, guidance in OBJECTION_RESPONSES.items():
        if any(word in objection_lower for word in key.split()):
            playbook_entry = guidance
            break

    lead_ctx = format_lead_context(lead)
    convo_text = _format_conversation(conversation_history[-8:])

    user_prompt = f"""The lead raised this objection: "{objection}"

Lead context:
{lead_ctx}

Recent conversation:
{convo_text}

Objection handling guidance:
{playbook_entry or "Address the concern directly, acknowledge it genuinely, then reframe."}

Write a response that:
- Acknowledges their concern first (1 sentence max)
- Reframes or addresses it concisely (1–2 sentences)
- Ends with a question or clear next step (1 sentence)
- Total: max 4 sentences
- Tone: confident, human, not defensive

Response only — no labels or preamble."""

    from app.services.outreach_composer import OUTREACH_SYSTEM
    return await complete(
        system=OUTREACH_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=300,
        temperature=0.7,
    )
