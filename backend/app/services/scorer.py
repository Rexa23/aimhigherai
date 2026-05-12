"""
Engagement Scoring Engine.

Score = weighted sum of 5 dimensions, normalized to 0–100.

Dimensions:
  1. Market Cap Position    (25 pts) — how well it fits the 30k–3M sweet spot
  2. Pain Signal Density    (25 pts) — number and specificity of pain signals
  3. Engagement Rate        (20 pts) — likes/replies/RTs relative to audience
  4. Activity Recency       (15 pts) — how recently the project was active
  5. Community Size Proxy   (15 pts) — combined follower/member count signal

Priority thresholds (from settings):
  HOT  >= 75
  WARM >= 45
  COLD  < 45
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.models.lead import LeadPriority


# ── Score breakdown ────────────────────────────────────────────────────────────

@dataclass
class ScoreBreakdown:
    market_cap_score:   float  # 0–25
    pain_signal_score:  float  # 0–25
    engagement_score:   float  # 0–20
    recency_score:      float  # 0–15
    community_score:    float  # 0–15
    total:              float  # 0–100
    priority:           LeadPriority
    rationale:          list[str]


# ── 1. Market cap position (25 pts) ──────────────────────────────────────────
# Sweet spot: 100k–800k = max score. Taper off toward edges of 30k–3M range.

def _market_cap_score(market_cap_usd: float) -> float:
    low  = settings.MARKET_CAP_MIN   # 30_000
    high = settings.MARKET_CAP_MAX   # 3_000_000
    sweet_low  = 100_000
    sweet_high = 800_000

    if market_cap_usd < low or market_cap_usd > high:
        return 0.0

    if sweet_low <= market_cap_usd <= sweet_high:
        return 25.0

    if market_cap_usd < sweet_low:
        # Linear ramp from low→sweet_low: 10→25
        frac = (market_cap_usd - low) / (sweet_low - low)
        return 10.0 + frac * 15.0

    # Linear drop from sweet_high→high: 25→10
    frac = (market_cap_usd - sweet_high) / (high - sweet_high)
    return 25.0 - frac * 15.0


# ── 2. Pain signal density (25 pts) ──────────────────────────────────────────
# Each distinct pain signal = 6 pts, capped at 4 signals (24 pts) + 1 bonus for specificity.

def _pain_signal_score(pain_signals: list[str]) -> float:
    n = len(pain_signals)
    if n == 0:
        return 0.0
    base = min(n, 4) * 6.0
    # Bonus: if any signal > 30 chars, it's specific (not just a keyword match)
    specificity_bonus = 1.0 if any(len(s) > 30 for s in pain_signals) else 0.0
    return min(base + specificity_bonus, 25.0)


# ── 3. Engagement rate (20 pts) ───────────────────────────────────────────────
# engagement_rate is a percentage (0–100). Diminishing returns via log.

def _engagement_score(engagement_rate: float) -> float:
    if engagement_rate <= 0:
        return 0.0
    # log scale: 0.1% → ~6, 1% → ~13, 5% → ~18, 10%+ → 20
    score = 20.0 * (math.log(engagement_rate + 1) / math.log(11))
    return min(score, 20.0)


# ── 4. Activity recency (15 pts) ──────────────────────────────────────────────
# Full points if active within 1 hour. Linear decay to 0 at 14 days.

def _recency_score(last_activity_at: datetime | None) -> float:
    if last_activity_at is None:
        return 0.0
    now = datetime.now(timezone.utc)
    if last_activity_at.tzinfo is None:
        last_activity_at = last_activity_at.replace(tzinfo=timezone.utc)
    age_hours = (now - last_activity_at).total_seconds() / 3600
    max_hours = 14 * 24  # 14 days
    if age_hours >= max_hours:
        return 0.0
    return 15.0 * (1 - age_hours / max_hours)


# ── 5. Community size proxy (15 pts) ──────────────────────────────────────────
# Log scale across combined follower/member count.
# 100 → ~3, 1k → ~7, 5k → ~11, 25k → ~15

def _community_score(total_followers: int) -> float:
    if total_followers <= 0:
        return 0.0
    score = 15.0 * (math.log(total_followers + 1) / math.log(25_001))
    return min(score, 15.0)


# ── Master scorer ──────────────────────────────────────────────────────────────

def score_lead(
    market_cap_usd: float,
    pain_signals: list[str],
    engagement_rate: float,
    last_activity_at: datetime | None,
    twitter_followers: int = 0,
    telegram_members: int = 0,
    discord_members: int = 0,
    activity_metrics: dict[str, Any] | None = None,
) -> ScoreBreakdown:
    am = activity_metrics or {}
    total_community = twitter_followers + telegram_members + discord_members

    mc_score   = _market_cap_score(market_cap_usd)
    ps_score   = _pain_signal_score(pain_signals)
    eng_score  = _engagement_score(engagement_rate)
    rec_score  = _recency_score(last_activity_at)
    comm_score = _community_score(total_community)

    total = mc_score + ps_score + eng_score + rec_score + comm_score
    total = round(min(total, 100.0), 2)

    if total >= settings.SCORE_HOT_THRESHOLD:
        priority = LeadPriority.HOT
    elif total >= settings.SCORE_WARM_THRESHOLD:
        priority = LeadPriority.WARM
    else:
        priority = LeadPriority.COLD

    rationale: list[str] = []
    if mc_score >= 20:
        rationale.append(f"Market cap ${market_cap_usd:,.0f} is in the sweet spot")
    if ps_score >= 12:
        rationale.append(f"{len(pain_signals)} pain signal(s) detected")
    if eng_score >= 12:
        rationale.append(f"Strong engagement rate: {engagement_rate:.2f}%")
    if rec_score >= 10:
        rationale.append("Recently active community")
    if comm_score >= 10:
        rationale.append(f"Community size: {total_community:,} across platforms")
    if not rationale:
        rationale.append("Low signal — monitor only")

    return ScoreBreakdown(
        market_cap_score=round(mc_score, 2),
        pain_signal_score=round(ps_score, 2),
        engagement_score=round(eng_score, 2),
        recency_score=round(rec_score, 2),
        community_score=round(comm_score, 2),
        total=total,
        priority=priority,
        rationale=rationale,
    )
