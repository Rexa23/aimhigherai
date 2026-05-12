from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List, Optional


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────
    APP_NAME: str = "AimHigher AI Onboarding"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str
    FRONTEND_URL: str = "http://localhost:3000"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_QUEUE_TTL: int = 86400
    REDIS_FOLLOWUP_TTL: int = 604800

    # ── Gemini (Google) ───────────────────────────────────────────────────
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_MAX_TOKENS: int = 2048

    # ── Twitter / X ───────────────────────────────────────────────────────
    TWITTER_BEARER_TOKEN: str
    TWITTER_API_KEY: str
    TWITTER_API_SECRET: str
    TWITTER_ACCESS_TOKEN: str
    TWITTER_ACCESS_SECRET: str

    # ── Telegram ──────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str

    # ── Discord ───────────────────────────────────────────────────────────
    DISCORD_ENABLED: bool = False
    DISCORD_BOT_TOKEN: str


    # ── Onchain ───────────────────────────────────────────────────────────
    DEXSCREENER_BASE_URL: str = "https://api.dexscreener.com/latest"
    MORALIS_API_KEY: str
    COVALENT_API_KEY: str

    # ── Vector DB ─────────────────────────────────────────────────────────
    PINECONE_API_KEY: str
    PINECONE_ENVIRONMENT: str
    PINECONE_INDEX: str = "aimhigherai"   # matches what you created in Pinecone
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_API_KEY: str

    # ── Hunter settings ───────────────────────────────────────────────────
    MARKET_CAP_MIN: float = 30_000
    MARKET_CAP_MAX: float = 3_000_000
    HUNTER_INTERVAL_SECONDS: int = 1800
    SCORE_HOT_THRESHOLD: float = 75.0
    SCORE_WARM_THRESHOLD: float = 45.0

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
