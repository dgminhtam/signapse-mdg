import logging
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings
from app.core.observability import log_failure
from app.domain.errors import DatabaseUnavailableError

logger = logging.getLogger(__name__)


@lru_cache
def _build_database(
    database_url: str,
    pool_size: int,
    max_overflow: int,
    pool_timeout: float,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_pre_ping=True,
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[AsyncSession]:
    if settings.database_url is None:
        error = DatabaseUnavailableError(
            operation="database.get_session",
            failure_reason="DATABASE_QUERY_FAILED",
        )
        log_failure(logger, "database_not_configured", error)
        raise error

    _, session_factory = _build_database(
        settings.database_url,
        settings.database_pool_size,
        settings.database_pool_max_overflow,
        settings.database_pool_timeout_seconds,
    )
    async with session_factory() as session:
        yield session


def get_session_factory(
    settings: Annotated[Settings, Depends(get_settings)],
) -> async_sessionmaker[AsyncSession]:
    if settings.database_url is None:
        error = DatabaseUnavailableError(operation="database.get_session_factory")
        log_failure(logger, "database_not_configured", error)
        raise error
    _, session_factory = _build_database(
        settings.database_url,
        settings.database_pool_size,
        settings.database_pool_max_overflow,
        settings.database_pool_timeout_seconds,
    )
    return session_factory


def build_session_factory(
    settings: Settings,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]] | None:
    if settings.database_url is None:
        return None
    return _build_database(
        settings.database_url,
        settings.database_pool_size,
        settings.database_pool_max_overflow,
        settings.database_pool_timeout_seconds,
    )
