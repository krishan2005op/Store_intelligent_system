from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.repositories import EventRepository, SQLAlchemyEventRepository


# Lazily create the async engine with retry logic.

def _create_engine():
    """Create the async engine, retrying a few times if the DB is not ready.
    This helps when the PostgreSQL container is still starting up when the
    FastAPI app imports this module.
    """
    import time
    from app.core.logging import get_logger

    logger = get_logger(__name__)
    for attempt in range(5):
        try:
            return create_async_engine(
                get_settings().database_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                connect_args={"command_timeout": 5},
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Database engine creation failed (attempt %s/5)", attempt + 1, exc_info=exc
            )
            time.sleep(2)
    # Final attempt – let any exception propagate.
    return create_async_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args={"command_timeout": 5},
    )

engine = _create_engine()

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    class_=AsyncSession,
)


async def get_async_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionFactory() as session:
        yield session


async def get_event_repository() -> AsyncIterator[EventRepository]:
    async for session in get_async_session():
        yield SQLAlchemyEventRepository(session)
