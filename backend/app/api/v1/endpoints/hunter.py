"""
/api/v1/hunter — trigger runs, check queue depth, review recent results
"""
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.db.session import get_db
from app.core.redis import get_redis, QueueName

router = APIRouter(prefix="/hunter", tags=["hunter"])

DbDep    = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]


@router.post("/run")
async def trigger_hunter_run(background_tasks: BackgroundTasks, redis: RedisDep):
    """Manually trigger a hunter run outside the scheduled interval."""
    from app.services.hunter import HunterOrchestrator
    hunter = HunterOrchestrator()

    async def _run():
        try:
            stats = await hunter.run()
            return stats
        finally:
            await hunter.close()

    background_tasks.add_task(_run)
    return {"status": "triggered", "message": "Hunter run started in background"}


@router.get("/queue-depth")
async def get_queue_depths(redis: RedisDep):
    """Return current depth of all task queues."""
    depths = {}
    for q in QueueName:
        depths[q.value] = await redis.llen(q.value)
    return depths


@router.get("/dead-letter")
async def get_dead_letter_items(redis: RedisDep, limit: int = 20):
    """Inspect failed tasks in the dead-letter queue."""
    import json
    items = await redis.lrange(QueueName.DEAD_LETTER.value, 0, limit - 1)
    return [json.loads(i) for i in items]


@router.delete("/dead-letter")
async def clear_dead_letter(redis: RedisDep):
    """Clear the dead-letter queue after review."""
    count = await redis.llen(QueueName.DEAD_LETTER.value)
    await redis.delete(QueueName.DEAD_LETTER.value)
    return {"cleared": count}
