"""
Twitter/X data adapter.
Uses Tweepy AsyncClient (OAuth2 Bearer Token) for v2 API search.
Respects rate limits: 500k tweets/month on Basic, 10 req/15 min on free.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import tweepy
import tweepy.asynchronous
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Keywords for lead discovery ───────────────────────────────────────────────

DISCOVERY_QUERIES = [
    # Project + chain signals
    "(token launch OR #tokenlaunch) (ethereum OR solana OR bnb OR base) -is:retweet lang:en",
    "(#newtoken OR #defi OR #web3) (community growth OR marketing) -is:retweet lang:en",
    "(#crypto) (\"low traction\" OR \"need exposure\" OR \"marketing not working\") -is:retweet lang:en",
    "(#NFT OR #DeFi OR #AI) (\"launch\" OR \"going live\") -is:retweet lang:en",
    "(#memecoin OR #altcoin) (\"join our community\" OR \"early community\") -is:retweet lang:en",
]

# ── Pain signals ──────────────────────────────────────────────────────────────

PAIN_PATTERNS = [
    r"marketing (not|isn'?t|doesn'?t) (work|working|convert)",
    r"(need|looking for) (exposure|visibility|marketing|promotions?)",
    r"(low|no|lack of) (traction|engagement|volume|trading)",
    r"(struggling|hard) (to|with) (grow|reach|market|get noticed)",
    r"(can't|cannot|hard to) (grow|reach|get) (community|audience|holders)",
    r"(spending on|wasted on) (marketing|ads|promotions?) (with|but) (no|little|zero) results?",
    r"(organic|real) (community|growth|engagement) (needed|wanted|looking for)",
    r"(bots|fake|paid) (followers|engagement|volume)",
    r"(burned|wasted) (money|budget) on (marketing|ads|kol)",
    r"how (do|can) (we|i) (grow|market) (our|a) (token|project|community)",
    r"(cex|exchange) (listing|volume|requirements?)",
    r"(failed|bad|terrible|zero) (marketing|campaign|results?)",
]

_PAIN_RE = [re.compile(p, re.IGNORECASE) for p in PAIN_PATTERNS]

# Shared with Discord/Telegram hunters for token ticker extraction.
TICKER_RE = re.compile(r"\$([A-Z]{2,10})\b")


@dataclass
class TwitterProfile:
    handle: str
    user_id: str
    name: str
    description: str
    followers: int
    following: int
    tweet_count: int
    verified: bool
    created_at: datetime | None
    profile_url: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class TwitterSignal:
    profile: TwitterProfile
    pain_signals: list[str]
    sample_tweets: list[str]
    engagement_rate: float
    tweet_frequency_7d: int
    last_tweet_at: datetime | None
    discovery_query: str


class TwitterHunter:
    def __init__(self):
        self._client = tweepy.asynchronous.AsyncClient(
            bearer_token=settings.TWITTER_BEARER_TOKEN,
            consumer_key=settings.TWITTER_API_KEY,
            consumer_secret=settings.TWITTER_API_SECRET,
            access_token=settings.TWITTER_ACCESS_TOKEN,
            access_token_secret=settings.TWITTER_ACCESS_SECRET,
            wait_on_rate_limit=True,
        )
        # Rate limit tracking: Basic tier = 1 request/second search
        self._last_search = 0.0
        self._min_interval = 1.2  # seconds between search calls

    async def _throttle(self) -> None:
        import time
        elapsed = time.monotonic() - self._last_search
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_search = time.monotonic()

    @retry(
        retry=retry_if_exception_type(tweepy.TooManyRequests),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=15, max=900),
    )
    async def search_recent(self, query: str, max_results: int = 100) -> list[dict]:
        await self._throttle()
        try:
            response = await self._client.search_recent_tweets(
                query=query,
                max_results=min(max_results, 100),
                tweet_fields=["author_id", "created_at", "public_metrics", "text", "entities"],
                user_fields=["name", "username", "public_metrics", "description", "created_at", "verified"],
                expansions=["author_id"],
                start_time=datetime.now(timezone.utc) - timedelta(days=7),
            )
        except tweepy.TooManyRequests:
            logger.warning("Twitter rate limit hit, backing off")
            raise
        except tweepy.TwitterServerError as e:
            logger.error(f"Twitter server error: {e}")
            return []

        if not response.data:
            return []

        # Build user lookup map
        users = {u.id: u for u in (response.includes.get("users") or [])}

        results = []
        for tweet in response.data:
            user = users.get(tweet.author_id)
            if user:
                results.append({"tweet": tweet, "user": user})
        return results

    @retry(
        retry=retry_if_exception_type(tweepy.TooManyRequests),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=15, max=300),
    )
    async def get_user_tweets(self, user_id: str, max_results: int = 20) -> list[Any]:
        await self._throttle()
        try:
            response = await self._client.get_users_tweets(
                id=user_id,
                max_results=min(max_results, 100),
                tweet_fields=["created_at", "public_metrics", "text"],
                start_time=datetime.now(timezone.utc) - timedelta(days=7),
            )
            return response.data or []
        except Exception as e:
            logger.debug(f"Failed to fetch user tweets for {user_id}: {e}")
            return []

    def detect_pain_signals(self, texts: list[str]) -> list[str]:
        signals = set()
        combined = " ".join(texts)
        for pattern in _PAIN_RE:
            match = pattern.search(combined)
            if match:
                # Extract the matched snippet (up to 80 chars) as the signal
                start = max(0, match.start() - 10)
                end = min(len(combined), match.end() + 10)
                signals.add(combined[start:end].strip())
        return list(signals)

    def calc_engagement_rate(self, tweets: list[Any], followers: int) -> float:
        if not tweets or followers == 0:
            return 0.0
        total_engagement = sum(
            (t.public_metrics.get("like_count", 0) +
             t.public_metrics.get("reply_count", 0) +
             t.public_metrics.get("retweet_count", 0))
            for t in tweets
        )
        avg_engagement = total_engagement / len(tweets)
        rate = (avg_engagement / followers) * 100
        return round(min(rate, 100.0), 4)

    async def hunt(self) -> list[TwitterSignal]:
        """
        Run all discovery queries and aggregate unique project signals.
        Deduplication by user_id.
        """
        seen_user_ids: set[str] = set()
        signals: list[TwitterSignal] = []

        for query in DISCOVERY_QUERIES:
            try:
                results = await self.search_recent(query, max_results=50)
                logger.info(f"Twitter query returned {len(results)} results: {query[:60]}")
            except Exception as e:
                logger.error(f"Twitter search failed for query '{query[:40]}': {e}")
                continue

            for item in results:
                user = item["user"]
                tweet = item["tweet"]
                user_id = str(user.id)

                if user_id in seen_user_ids:
                    continue
                seen_user_ids.add(user_id)

                # Skip accounts with fewer than 100 followers (too small)
                followers = user.public_metrics.get("followers_count", 0)
                if followers < 100:
                    continue

                # Fetch recent tweets for deeper analysis
                recent = await self.get_user_tweets(user_id, max_results=20)
                all_texts = [t.text for t in recent] + [tweet.text]

                pain_signals = self.detect_pain_signals(all_texts)
                engagement = self.calc_engagement_rate(recent, followers)
                last_tweet_at = None
                if recent:
                    last_tweet_at = max(
                        (t.created_at for t in recent if t.created_at),
                        default=None,
                    )

                profile = TwitterProfile(
                    handle=f"@{user.username}",
                    user_id=user_id,
                    name=user.name,
                    description=user.description or "",
                    followers=followers,
                    following=user.public_metrics.get("following_count", 0),
                    tweet_count=user.public_metrics.get("tweet_count", 0),
                    verified=bool(getattr(user, "verified", False)),
                    created_at=getattr(user, "created_at", None),
                    profile_url=f"https://twitter.com/{user.username}",
                    raw={"id": user_id, "username": user.username},
                )

                signals.append(TwitterSignal(
                    profile=profile,
                    pain_signals=pain_signals,
                    sample_tweets=all_texts[:5],
                    engagement_rate=engagement,
                    tweet_frequency_7d=len(recent),
                    last_tweet_at=last_tweet_at,
                    discovery_query=query,
                ))

        logger.info(f"Twitter hunt complete: {len(signals)} unique signals")
        return signals
