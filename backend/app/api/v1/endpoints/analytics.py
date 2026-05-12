"""
/api/v1/analytics — dashboard stats, daily metrics
/api/v1/agents    — toggle agents, adjust settings
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.db.crud import get_dashboard_stats
from app.db.session import get_db
from app.core.redis import (
    get_redis, get_all_agent_statuses, set_agent_enabled,
)
from app.schemas.lead import AgentStatus, AgentToggle, DashboardStats

analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])
agents_router    = APIRouter(prefix="/agents",    tags=["agents"])

DbDep    = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]


# ── Dashboard stats ───────────────────────────────────────────────────────────

@analytics_router.get("/dashboard", response_model=DashboardStats)
async def dashboard(db: DbDep):
    stats = await get_dashboard_stats(db)
    return DashboardStats(**stats)


# ── Agent controls ────────────────────────────────────────────────────────────

@agents_router.get("/status", response_model=AgentStatus)
async def agent_statuses(redis: RedisDep):
    statuses = await get_all_agent_statuses(redis)
    return AgentStatus(**statuses)


@agents_router.post("/toggle", response_model=AgentStatus)
async def toggle_agent(payload: AgentToggle, redis: RedisDep):
    await set_agent_enabled(redis, payload.agent, payload.enabled)
    statuses = await get_all_agent_statuses(redis)
    return AgentStatus(**statuses)
