"""
Redis connection pool, queue names, and task dispatch helpers.
Uses redis.asyncio for async FastAPI compatibility.
Queue pattern: Redis Streams for durable tasks, Sorted Sets for scheduled follow-ups.
"""
from __future__ import annotations
import json
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff

from app.core.config import settings

# ── Connection pool ───────────────────────────────────────────────────────────

_redis_client: Redis | None = None


async def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        retry = Retry(ExponentialBackoff(cap=10, base=0.5), retries=5)
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            retry=retry,
            retry_on_error=[ConnectionError, TimeoutError],
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


# ── Queue / stream names ──────────────────────────────────────────────────────

class QueueName(str, Enum):
    HUNTER_RESULTS   = "queue:hunter_results"    # Hunter → Orchestrator
    OUTREACH_TASKS   = "queue:outreach_tasks"    # Orchestrator → Outreach
    QUALIFY_TASKS    = "queue:qualify_tasks"     # Orchestrator → Qualification
    ONBOARDING_TASKS = "queue:onboarding_tasks"  # Orchestrator → Onboarding
    CONVERSION_TASKS = "queue:conversion_tasks"  # Orchestrator → Conversion
    REPLY_INGEST     = "queue:reply_ingest"      # Inbound webhooks
    DEAD_LETTER      = "queue:dead_letter"       # Failed tasks


class ScheduleKey(str, Enum):
    FOLLOWUPS = "schedule:followups"    # Sorted set: score = UNIX timestamp
    NUDGES    = "schedule:nudges"       # Sorted set: score = UNIX timestamp


class AgentLockKey(str, Enum):
    HUNTER       = "lock:agent:hunter"
    OUTREACH     = "lock:agent:outreach"
    QUALIFICATION = "lock:agent:qualification"
    ONBOARDING   = "lock:agent:onboarding"
    CONVERSION   = "lock:agent:conversion"


class AgentStatusKey(str, Enum):
    ENABLED_PREFIX = "agent:enabled:"   # agent:enabled:hunter = "1"/"0"


# ── Queue helpers ─────────────────────────────────────────────────────────────

async def enqueue(
    redis: Redis,
    queue: QueueName,
    payload: dict[str, Any],
    *,
    maxlen: int = 10_000,
) -> str:
    """Push a task onto a Redis list (LPUSH). Returns task ID."""
    task_id = str(uuid.uuid4())
    message = json.dumps({"task_id": task_id, "enqueued_at": time.time(), **payload})
    await redis.lpush(queue.value, message)
    # Trim to prevent unbounded growth
    await redis.ltrim(queue.value, 0, maxlen - 1)
    return task_id


async def dequeue(
    redis: Redis,
    queue: QueueName,
    timeout: int = 5,
) -> dict[str, Any] | None:
    """Blocking pop from queue. Returns None on timeout."""
    result = await redis.brpop(queue.value, timeout=timeout)
    if result is None:
        return None
    _, raw = result
    return json.loads(raw)


async def move_to_dead_letter(
    redis: Redis,
    original_queue: QueueName,
    payload: dict[str, Any],
    error: str,
) -> None:
    dead = {
        "original_queue": original_queue.value,
        "failed_at": datetime.utcnow().isoformat(),
        "error": error,
        **payload,
    }
    await redis.lpush(QueueName.DEAD_LETTER.value, json.dumps(dead))


# ── Scheduled task helpers (Sorted Set: score = UNIX timestamp) ───────────────

async def schedule_task(
    redis: Redis,
    key: ScheduleKey,
    payload: dict[str, Any],
    run_at: datetime,
) -> None:
    task_id = str(uuid.uuid4())
    member = json.dumps({"task_id": task_id, **payload})
    score = run_at.timestamp()
    await redis.zadd(key.value, {member: score})
    # TTL on the entire set to prevent ghost tasks
    await redis.expire(key.value, settings.REDIS_FOLLOWUP_TTL)


async def pop_due_tasks(
    redis: Redis,
    key: ScheduleKey,
    now: datetime | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Pop all tasks scheduled at or before now."""
    cutoff = (now or datetime.utcnow()).timestamp()
    raw_items = await redis.zrangebyscore(key.value, "-inf", cutoff, start=0, num=limit)
    if not raw_items:
        return []
    # Atomically remove the popped members
    async with redis.pipeline(transaction=True) as pipe:
        for item in raw_items:
            pipe.zrem(key.value, item)
        await pipe.execute()
    return [json.loads(item) for item in raw_items]


# ── Agent state helpers ────────────────────────────────────────────────────────

async def set_agent_enabled(redis: Redis, agent_name: str, enabled: bool) -> None:
    key = f"{AgentStatusKey.ENABLED_PREFIX.value}{agent_name}"
    await redis.set(key, "1" if enabled else "0")


async def is_agent_enabled(redis: Redis, agent_name: str) -> bool:
    key = f"{AgentStatusKey.ENABLED_PREFIX.value}{agent_name}"
    val = await redis.get(key)
    if val is None:
        return True  # default: enabled
    return val == "1"


async def get_all_agent_statuses(redis: Redis) -> dict[str, bool]:
    agents = ["hunter", "outreach", "qualification", "onboarding", "conversion"]
    results = {}
    for name in agents:
        results[name] = await is_agent_enabled(redis, name)
    return results


# ── Distributed lock (prevents duplicate hunter runs) ─────────────────────────

class RedisLock:
    def __init__(self, redis: Redis, key: AgentLockKey, ttl: int = 300):
        self.redis = redis
        self.key = key.value
        self.ttl = ttl
        self._lock_id = str(uuid.uuid4())

    async def acquire(self) -> bool:
        result = await self.redis.set(
            self.key, self._lock_id, nx=True, ex=self.ttl
        )
        return result is True

    async def release(self) -> None:
        current = await self.redis.get(self.key)
        if current == self._lock_id:
            await self.redis.delete(self.key)

    async def __aenter__(self) -> "RedisLock":
        acquired = await self.acquire()
        if not acquired:
            raise RuntimeError(f"Could not acquire lock: {self.key}")
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.release()


# ── Caching helpers ────────────────────────────────────────────────────────────

async def cache_set(
    redis: Redis,
    key: str,
    value: Any,
    ttl: int = 300,
) -> None:
    await redis.set(f"cache:{key}", json.dumps(value), ex=ttl)


async def cache_get(redis: Redis, key: str) -> Any | None:
    raw = await redis.get(f"cache:{key}")
    if raw is None:
        return None
    return json.loads(raw)


async def cache_invalidate(redis: Redis, key: str) -> None:
    await redis.delete(f"cache:{key}")
