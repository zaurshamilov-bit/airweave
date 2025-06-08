"""Database session configuration."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from airweave.core.config import settings

async_engine = create_async_engine(
    str(settings.SQLALCHEMY_ASYNC_DATABASE_URI),
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=300,  # Recycle connections after 5 minutes
    pool_timeout=30,
    isolation_level="READ COMMITTED",
    # New settings to prevent connection buildup:
    connect_args={
        "server_settings": {
            "idle_in_transaction_session_timeout": "60000",  # Kill idle transactions after 60s
        },
        "command_timeout": 60,
    },
)
AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=async_engine)


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session that can be used as a context manager.

    Yields:
        AsyncSession: An async database session

    Example:
    -------
        async with get_db_context() as db:
            await db.execute(...)

    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session to be used in dependency injection.

    Yields:
    ------
        AsyncSession: An async database session

    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()
