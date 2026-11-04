import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import EconomicCalendarEventModel
from app.db.repositories import PostgresEconomicCalendarRepository
from app.domain.errors import ProviderUnavailableError
from app.services.economic_calendar_refresh import EconomicCalendarRefreshService
from tests.unit.test_mt5_calendar_transport import connect, provider_for, response

pytestmark = pytest.mark.integration


async def test_second_rpc_partial_does_not_commit_first_page(database_engine, tmp_path):
    repository = PostgresEconomicCalendarRepository(async_sessionmaker(database_engine))
    provider = provider_for(tmp_path)
    await provider.start()
    reader, writer = await connect(provider)
    service = EconomicCalendarRefreshService(
        provider, repository, clock=lambda: datetime(2026, 11, 4, tzinfo=UTC)
    )
    task = asyncio.create_task(service.refresh())
    try:
        await response(reader, writer)
        await response(reader, writer, incomplete=True)
        with pytest.raises(ProviderUnavailableError):
            await task
        async with database_engine.connect() as connection:
            count = await connection.scalar(
                select(func.count()).select_from(EconomicCalendarEventModel)
            )
        assert count == 0
    finally:
        await provider.close()
        writer.close()
        await writer.wait_closed()
