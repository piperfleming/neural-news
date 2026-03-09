"""Async SQLAlchemy engine and session for Postgres."""
import ssl
from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.base import Base
from app.models import (  # noqa: F401 - register tables with Base.metadata
    Article,
    ArticleComment,
    ArticleClick,
    ArticleLike,
    BriefingFeedback,
    DailyBriefing,
    User,
    UserSession,
)

# ── Prepare the database URL and connect_args ────────────────────────
# asyncpg does NOT understand libpq-specific query params like
# `sslmode` and `channel_binding`. We strip them from the URL and
# handle SSL ourselves via connect_args.

_raw_url = settings.database_url
_connect_args: dict = {}

_needs_ssl = "sslmode=require" in _raw_url

# Strip params that asyncpg can't handle
_STRIP_PARAMS = {"sslmode", "channel_binding"}
_parsed = urlparse(_raw_url)
_qs = parse_qs(_parsed.query)
_filtered_qs = {k: v for k, v in _qs.items() if k not in _STRIP_PARAMS}
_clean_url = urlunparse(_parsed._replace(query=urlencode(_filtered_qs, doseq=True)))

if _needs_ssl:
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    _connect_args["ssl"] = ssl_context

engine = create_async_engine(
    _clean_url,
    echo=settings.debug,
    future=True,
    connect_args=_connect_args,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create tables (for development; use Alembic for production migrations)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add columns that were added to the model after the table was first created
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(100)"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS custom_interests TEXT"))
        await conn.execute(text("ALTER TABLE daily_briefings ADD COLUMN IF NOT EXISTS topic_outline TEXT"))
        await conn.execute(text("ALTER TABLE daily_briefings ADD COLUMN IF NOT EXISTS detail_level INTEGER NOT NULL DEFAULT 4"))
        await conn.execute(text("ALTER TABLE daily_briefings ADD COLUMN IF NOT EXISTS source_context TEXT"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_detail_level INTEGER"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS theme_config JSONB"))
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_daily_briefing BOOLEAN NOT NULL DEFAULT FALSE"
        ))
