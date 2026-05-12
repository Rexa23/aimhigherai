"""
FastAPI application factory with lifespan management, CORS,
WebSocket broadcast for real-time dashboard updates, and health check.
"""
from __future__ import annotations
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.redis import close_redis, get_redis
from app.db.session import engine

logger = logging.getLogger("aimhigher")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
)


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active = [c for c in self.active if c is not ws]

    async def broadcast(self, data: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for connection in self.active:
            try:
                await connection.send_text(json.dumps(data))
            except Exception:
                dead.append(connection)
        for d in dead:
            self.disconnect(d)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AimHigher backend...")

    redis = await get_redis()
    await redis.ping()
    logger.info("Redis connected")

    # Verify DB connection
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connected")

    # Register shared singletons — avoids circular imports in agents/services
    from app.services import ws_registry
    ws_registry.register_manager(manager)

    from app.services.hunter import HunterOrchestrator, run_hunter_loop
    from app.services.telegram_hunter import TelegramHunter

    hunter = HunterOrchestrator()
    app.state.hunter = hunter

    discord_bot = None
    if settings.DISCORD_ENABLED:
        from app.services import discord_registry
        from app.services.discord_hunter import DiscordHunter

        discord_bot = DiscordHunter()
        discord_bot.add_signal_callback(hunter.ingest_discord_signal)
        app.state.discord_bot = discord_bot

        # Populate module-level registry so outreach_worker can DM without circular import
        discord_registry.register_bot(discord_bot)
    else:
        logger.info("Discord bot disabled by configuration")

    from app.services.outreach_worker import OutreachWorker
    from app.agents.qualification_worker import QualificationWorker
    from app.agents.onboarding_worker import OnboardingWorker
    from app.agents.conversion import ConversionEngine
    from app.agents.orchestrator import Orchestrator

    outreach_worker      = OutreachWorker(telegram=TelegramHunter())
    qualification_worker = QualificationWorker()
    onboarding_worker    = OnboardingWorker()
    app.state.onboarding_worker = onboarding_worker
    conversion_engine = ConversionEngine()
    orchestrator      = Orchestrator()
    app.state.conversion_engine = conversion_engine
    app.state.orchestrator      = orchestrator
    app.state.outreach_worker      = outreach_worker
    app.state.qualification_worker = qualification_worker

    tasks: list[asyncio.Task] = [
        asyncio.create_task(run_hunter_loop(hunter),              name="hunter_loop"),
        asyncio.create_task(_followup_scheduler(),                name="followup_scheduler"),
        asyncio.create_task(outreach_worker.run_forever(),        name="outreach_worker"),
        asyncio.create_task(qualification_worker.run_forever(),   name="qualification_worker"),
        asyncio.create_task(onboarding_worker.run_forever(),      name="onboarding_worker"),
        asyncio.create_task(conversion_engine.run_forever(),     name="conversion_engine"),
        asyncio.create_task(orchestrator.run_forever(),          name="orchestrator"),
    ]

    if discord_bot is not None:
        tasks.insert(2, asyncio.create_task(discord_bot.start_bot(), name="discord_bot"))

    logger.info("AimHigher backend ready")
    yield

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    await hunter.close()
    await close_redis()
    await engine.dispose()
    logger.info("AimHigher backend shut down cleanly")


async def _followup_scheduler() -> None:
    from app.core.redis import ScheduleKey, pop_due_tasks, QueueName, enqueue
    while True:
        try:
            await asyncio.sleep(60)
            redis = await get_redis()
            tasks = await pop_due_tasks(redis, ScheduleKey.FOLLOWUPS)
            for task in tasks:
                await enqueue(redis, QueueName.OUTREACH_TASKS, {"type": "followup", **task})
                logger.info(f"Dispatched follow-up: {task.get('followup_id')}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Follow-up scheduler error: {e}")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await manager.connect(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(ws)

    @app.get("/health", tags=["health"])
    async def health():
        redis = await get_redis()
        redis_ok = await redis.ping()
        return {"status": "ok", "redis": "ok" if redis_ok else "error", "version": settings.APP_VERSION}

    return app


app = create_app()
