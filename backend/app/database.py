"""Async SQLAlchemy engine and session for Postgres."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.base import Base
from app.models import Article  # noqa: F401 - register table with Base.metadata

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
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
