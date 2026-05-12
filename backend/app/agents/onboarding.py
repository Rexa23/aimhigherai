"""
Onboarding Agent.
Guides a qualified project through opening a pool on AimHigher.

Pipeline per turn:
  1. Retrieve relevant knowledge base chunks (RAG)
  2. Determine current onboarding step from lead state
  3. Build context: lead data + memory + retrieved docs + conversation history
  4. Generate step-specific response via Claude
  5. Detect if step is complete → advance step counter
  6. Return reply + sources + next_action signal
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.gemini_client import complete, complete_json, format_lead_context
from app.services.vector_store import search_knowledge_base

logger = logging.getLogger(__name__)

# ── Onboarding steps ──────────────────────────────────────────────────────────
# Each step has: name, goal, and a completion signal to detect in the conversation.

ONBOARDING_STEPS = [
    {
        "step": 0,
        "name": "introduction",
        "goal": "Explain what AimHigher is and how campaign pools work. Gauge interest.",
        "completion_signal": "lead confirms they understand the concept and want to know more",
    },
    {
        "step": 1,
        "name": "fit_assessment",
        "goal": "Confirm the project fits AimHigher (chain, market cap, community size). Address any mismatch.",
        "completion_signal": "confirmed the project is eligible and on a supported chain",
    },
    {
        "step": 2,
        "name": "campaign_design",
        "goal": "Help them think through what tasks their community would complete: Twitter follows, Telegram joins, on-chain interactions, content creation.",
        "completion_signal": "project has described at least one campaign task type they want",
    },
    {
        "step": 3,
        "name": "budget_discussion",
        "goal": "Discuss pool budget. Minimum is [as per AimHigher docs]. Frame as pay-for-performance.",
        "completion_signal": "project has acknowledged the budget requirement or stated their budget range",
    },
    {
        "step": 4,
        "name": "roi_demonstration",
        "goal": "Show concrete ROI: holders acquired, wallet engagement, volume uplift from past campaigns. Handle 'need proof' objection.",
        "completion_signal": "project seems convinced or has asked how to get started",
    },
    {
        "step": 5,
        "name": "trust_and_mechanics",
        "goal": "Explain: non-custodial pool, smart contract release, how tasks are verified, how rewards are distributed.",
        "completion_signal": "project has no further trust questions and understands the mechanics",
    },
    {
        "step": 6,
        "name": "pool_creation_guide",
        "goal": "Walk them through the actual pool creation steps on AimHigher.gg step by step.",
        "completion_signal": "project has confirmed they are creating or have created the pool",
    },
    {
        "step": 7,
        "name": "converted",
        "goal": "Pool is live. Congratulate, set expectations for campaign results, offer support.",
        "completion_signal": "pool is confirmed live",
    },
]

MAX_STEP = len(ONBOARDING_STEPS) - 1

# ── System prompt ─────────────────────────────────────────────────────────────

ONBOARDING_SYSTEM = """You are the AimHigher Onboarding Specialist — an expert on the AimHigher platform who guides Web3 projects through launching their first campaign pool.

You have deep knowledge of:
- How AimHigher campaign pools work
- The supported chains: Ethereum, BNB Chain, Solana, Base
- Task types: social follows, Discord joins, on-chain interactions, content creation
- Pricing model: pay per completed task, budget deposited into pool
- Smart contract mechanics: non-custodial, task verification, reward release
- Common objections and how to address them

TONE:
- Knowledgeable but approachable. Not salesy — you're a guide, not a closer.
- Specific and concrete. No vague promises. Use numbers when available.
- Patient. If they ask the same thing twice, explain it differently.
- Proactive: if you detect confusion, clarify before they have to ask.

CRITICAL RULES:
- ONLY use information from the provided knowledge base excerpts and your training on AimHigher.
- If a question isn't covered by your knowledge base, say so clearly and offer to find out.
- Never invent platform features, pricing, or timelines.
- Never use AI phrases: "certainly", "of course", "I'd be happy to", "as an AI".
- Keep responses under 150 words unless explaining a multi-step process.
- Always end with a clear next step or question to keep momentum.
"""


# ── Main response generator ───────────────────────────────────────────────────

async def generate_onboarding_response(
    lead: dict[str, Any],
    conversation_history: list[dict[str, str]],
    user_message: str,
    current_step: int,
) -> dict[str, Any]:
    """
    Returns:
    {
      reply: str,
      sources_used: list[str],
      step_complete: bool,
      next_step: int,
      next_action: str | None,
    }
    """
    step_info = ONBOARDING_STEPS[min(current_step, MAX_STEP)]

    # ── RAG retrieval ─────────────────────────────────────────────────────────
    search_query = f"{step_info['name']} AimHigher {user_message}"
    retrieved    = await search_knowledge_base(search_query, top_k=4, score_threshold=0.28)

    rag_context = ""
    sources_used = []
    if retrieved:
        rag_context = "\n\nKNOWLEDGE BASE EXCERPTS (use these to answer accurately):\n"
        for chunk in retrieved:
            rag_context += f"\n[Source: {chunk.source_title}]\n{chunk.chunk}\n"
            if chunk.source_title not in sources_used:
                sources_used.append(chunk.source_title)

    # ── Build system with full context ───────────────────────────────────────
    lead_ctx = format_lead_context(lead)
    system = (
        ONBOARDING_SYSTEM
        + f"\n\nCURRENT LEAD:\n{lead_ctx}"
        + f"\n\nCURRENT ONBOARDING STEP: {current_step} — {step_info['name']}"
        + f"\nSTEP GOAL: {step_info['goal']}"
        + rag_context
    )

    # ── Build messages ────────────────────────────────────────────────────────
    from app.services.gemini_client import build_conversation_messages
    messages = build_conversation_messages(
        history=conversation_history,
        new_user_message=user_message,
        max_turns=20,
    )

    reply = await complete(
        system=system,
        messages=messages,
        max_tokens=500,
        temperature=0.5,   # lower for accuracy in onboarding context
    )

    # ── Detect step completion ────────────────────────────────────────────────
    step_complete = await _detect_step_completion(
        step_info=step_info,
        user_message=user_message,
        assistant_reply=reply,
        conversation_history=conversation_history[-4:],
    )

    next_step = current_step
    next_action = None

    if step_complete and current_step < MAX_STEP:
        next_step = current_step + 1
        logger.info(f"Onboarding step {current_step}→{next_step} for {lead.get('project_name')}")

    if next_step == MAX_STEP:
        next_action = "pool_creation"
    elif next_step > MAX_STEP or (step_complete and current_step == MAX_STEP):
        next_action = "converted"

    return {
        "reply":        reply.strip(),
        "sources_used": sources_used,
        "step_complete": step_complete,
        "next_step":    next_step,
        "next_action":  next_action,
    }


async def _detect_step_completion(
    step_info: dict[str, Any],
    user_message: str,
    assistant_reply: str,
    conversation_history: list[dict[str, str]],
) -> bool:
    """
    Ask Claude to assess whether the step completion signal has been reached.
    Uses a lightweight JSON call to avoid false positives.
    """
    recent = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in conversation_history
    )

    prompt = f"""Has this onboarding step been completed?

Step goal: {step_info['goal']}
Completion signal: {step_info['completion_signal']}

Recent exchange:
{recent}
LEAD: {user_message}
ASSISTANT: {assistant_reply}

Answer with JSON: {{"complete": true}} or {{"complete": false}}
Err on the side of false if uncertain."""

    try:
        result = await complete_json(
            system="You are an onboarding step tracker. Return only valid JSON.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
        )
        return bool(result.get("complete", False))
    except Exception:
        return False


# ── Step intro generator ──────────────────────────────────────────────────────

async def generate_step_intro(
    lead: dict[str, Any],
    step: int,
) -> str:
    """
    Generate the first message when entering a new onboarding step.
    Called when the orchestrator advances a lead to a new step.
    """
    step_info = ONBOARDING_STEPS[min(step, MAX_STEP)]
    retrieved = await search_knowledge_base(
        f"AimHigher {step_info['name']}", top_k=3, score_threshold=0.28
    )

    rag_context = ""
    if retrieved:
        rag_context = "\nKnowledge:\n" + "\n".join(c.chunk for c in retrieved[:2])

    lead_ctx = format_lead_context(lead)

    user_prompt = f"""Start onboarding step {step}: {step_info['name']}

Lead: {lead_ctx}
Step goal: {step_info['goal']}
{rag_context}

Write a natural transition message that:
- Acknowledges where we are in the process (without being robotic about it)
- Opens the topic for this step naturally
- Asks the first relevant question to start the step
- Max 3 sentences
"""

    return await complete(
        system=ONBOARDING_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=200,
        temperature=0.6,
    )
