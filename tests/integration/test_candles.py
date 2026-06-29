import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from alembic import command
from app.api.routes_candles import get_candle_provider, get_candle_repository
from app.cache.candle_cache import CandleCache
from app.cache.quote_cache import QuoteCache
from app.core.config import get_settings
from app.db.repositories import PostgresCandleRepository
from app.domain.candles import Candle
from app.domain.streams import ProviderStreamEvent, StreamCandle, StreamRequest
from app.domain.symbols import SupportedSymbol
from app.main import app
from app.services.stream_manager import StreamManager

pytestmark = pytest.mark.integration

START = datetime(2026, 6, 19, 0, 0, tzinfo=UTC)
BTC = SupportedSymbol("BTC/USD", "CRYPTO", "TWELVE_DATA", "BTC/USD", True)


def make_candle(open_time: datetime, close: str = "10.50") -> Candle:
    return Candle(
        symbol=BTC.symbol,
        asset_class=BTC.asset_class,
        provider=BTC.provider,
        provider_symbol=BTC.provider_symbol,
        timeframe="1m",
        open_time=open_time,
        close_time=open_time + timedelta(minutes=1) - timedelta(milliseconds=1),
        open=Decimal("10.00"),
        high=Decimal("11.00"),
        low=Decimal("9.00"),
        close=Decimal(close),
        volume=Decimal("12.340"),
        complete=False,
    )


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, datetime, datetime]] = []

    async def fetch_candles(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[Candle]:
        del timeframe, provider_interval, limit
        self.calls.append((symbol.provider_symbol, start, end))
        return [make_candle(cursor) for cursor in _slots(start, end)]


def _slots(start: datetime, end: datetime) -> list[datetime]:
    values: list[datetime] = []
    cursor = start
    while cursor < end:
        values.append(cursor)
        cursor += timedelta(minutes=1)
    return values


async def test_candle_migration_has_expected_schema_and_constraints(
    database_engine: AsyncEngine,
) -> None:
    async with database_engine.connect() as connection:
        columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"]
                for column in inspect(sync_connection).get_columns("market_data_candles")
            }
        )
        constraints = await connection.run_sync(
            lambda sync_connection: {
                tuple(constraint["column_names"])
                for constraint in inspect(sync_connection).get_unique_constraints(
                    "market_data_candles"
                )
            }
        )
    assert {
        "id",
        "symbol",
        "asset_class",
        "provider",
        "provider_symbol",
        "timeframe",
        "open_time",
        "close_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "complete",
        "created_at",
        "updated_at",
    } == columns
    assert ("provider", "provider_symbol", "timeframe", "open_time") in constraints


async def test_repository_upsert_is_idempotent_and_query_is_ordered(
    database_engine: AsyncEngine,
) -> None:
    repository = PostgresCandleRepository(async_sessionmaker(database_engine))
    later = make_candle(START + timedelta(minutes=1), close="20.00")
    earlier = make_candle(START, close="10.00")
    await repository.upsert_complete(
        [
            replace(earlier, complete=True),
        ]
    )
    await repository.upsert_complete(
        [
            replace(later, complete=True),
            replace(earlier, close=Decimal("10.25"), complete=True),
        ]
    )

    rows = await repository.list_complete(
        BTC,
        "1m",
        START,
        START + timedelta(minutes=2),
    )

    assert [row.open_time for row in rows] == [START, START + timedelta(minutes=1)]
    assert rows[0].close == Decimal("10.25")


async def test_forex_weekend_cleanup_migration_scope(
    migrated_database_url: str,
    database_engine: AsyncEngine,
) -> None:
    del migrated_database_url
    config = Config("alembic.ini")
    command.downgrade(config, "20260622_0003")
    rows = [
        ("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", "1h", datetime(2026, 6, 19, 20, tzinfo=UTC)),
        ("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", "1h", datetime(2026, 6, 19, 21, tzinfo=UTC)),
        ("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", "1h", datetime(2026, 6, 20, 0, tzinfo=UTC)),
        ("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", "1h", datetime(2026, 6, 21, 20, tzinfo=UTC)),
        ("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", "1h", datetime(2026, 6, 21, 21, tzinfo=UTC)),
        ("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", "1d", datetime(2026, 6, 19, tzinfo=UTC)),
        ("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", "1d", datetime(2026, 6, 20, tzinfo=UTC)),
        ("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", "1h", datetime(2026, 6, 20, 0, tzinfo=UTC)),
    ]
    async with database_engine.begin() as connection:
        for symbol, asset_class, provider, provider_symbol, timeframe, open_time in rows:
            await connection.execute(
                text(
                    """
                    INSERT INTO market_data_candles (
                        symbol,
                        asset_class,
                        provider,
                        provider_symbol,
                        timeframe,
                        open_time,
                        close_time,
                        open,
                        high,
                        low,
                        close,
                        volume,
                        complete
                    )
                    VALUES (
                        :symbol,
                        :asset_class,
                        :provider,
                        :provider_symbol,
                        :timeframe,
                        :open_time,
                        :close_time,
                        1,
                        1,
                        1,
                        1,
                        0,
                        true
                    )
                    """
                ),
                {
                    "symbol": symbol,
                    "asset_class": asset_class,
                    "provider": provider,
                    "provider_symbol": provider_symbol,
                    "timeframe": timeframe,
                    "open_time": open_time,
                    "close_time": open_time + timedelta(hours=1),
                },
            )

    command.upgrade(config, "head")

    async with database_engine.connect() as connection:
        remaining = await connection.execute(
            text(
                """
                SELECT symbol, asset_class, timeframe, open_time
                FROM market_data_candles
                ORDER BY asset_class, timeframe, open_time
                """
            )
        )

    assert [(row.symbol, row.asset_class, row.timeframe, row.open_time) for row in remaining] == [
        ("BTC/USD", "CRYPTO", "1h", datetime(2026, 6, 20, 0, tzinfo=UTC)),
        ("EUR/USD", "FOREX", "1d", datetime(2026, 6, 19, tzinfo=UTC)),
        ("EUR/USD", "FOREX", "1h", datetime(2026, 6, 19, 20, tzinfo=UTC)),
        ("EUR/USD", "FOREX", "1h", datetime(2026, 6, 21, 21, tzinfo=UTC)),
    ]

    command.downgrade(config, "20260622_0003")
    command.upgrade(config, "head")


async def test_cold_repeated_and_partial_requests_use_persisted_provider_mapping(
    database_engine: AsyncEngine,
) -> None:
    del database_engine
    provider = FakeProvider()
    app.dependency_overrides[get_candle_provider] = lambda: provider
    get_settings.cache_clear()
    transport = ASGITransport(app=app)
    params = {
        "symbol": "BTC/USD",
        "timeframe": "1m",
        "from": "2026-06-19T00:00:00Z",
        "to": "2026-06-19T00:02:00Z",
    }
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.get("/v1/candles", params=params)
            second = await client.get("/v1/candles", params=params)
            partial_params = dict(params)
            partial_params["to"] = "2026-06-19T00:03:00Z"
            partial = await client.get("/v1/candles", params=partial_params)
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 200
    assert partial.status_code == 200
    assert provider.calls == [
        ("BTC/USD", START, START + timedelta(minutes=2)),
        (
            "BTC/USD",
            START + timedelta(minutes=2),
            START + timedelta(minutes=3),
        ),
    ]
    assert len(partial.json()["candles"]) == 3


async def test_current_forming_candle_is_not_persisted(
    database_engine: AsyncEngine,
) -> None:
    current_start = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(minutes=1)

    class FormingProvider(FakeProvider):
        async def fetch_candles(
            self,
            symbol: SupportedSymbol,
            timeframe: str,
            provider_interval: str,
            start: datetime,
            end: datetime,
            limit: int,
        ) -> list[Candle]:
            del timeframe, provider_interval, end, limit
            candle = make_candle(start)
            return [
                Candle(
                    symbol=symbol.symbol,
                    asset_class=symbol.asset_class,
                    provider=symbol.provider,
                    provider_symbol=symbol.provider_symbol,
                    timeframe=candle.timeframe,
                    open_time=candle.open_time,
                    close_time=candle.close_time,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                    complete=False,
                )
            ]

    app.dependency_overrides[get_candle_provider] = lambda: FormingProvider()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/v1/candles",
                params={
                    "symbol": "BTC/USD",
                    "timeframe": "1m",
                    "from": current_start.isoformat().replace("+00:00", "Z"),
                    "to": (current_start + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
                },
            )
    finally:
        app.dependency_overrides.clear()

    async with database_engine.connect() as connection:
        count = await connection.scalar(
            text(
                """
                SELECT count(*)
                FROM market_data_candles
                WHERE open_time = :open_time
                """
            ),
            {"open_time": current_start},
        )

    assert response.status_code == 200
    assert response.json()["candles"][0]["complete"] is False
    assert count == 0


async def test_repository_read_scope_closes_before_provider_wait() -> None:
    class TrackingRepository:
        def __init__(self) -> None:
            self.read_active = False

        async def get_enabled_symbol(self, symbol: str) -> SupportedSymbol | None:
            del symbol
            return BTC

        async def list_complete(
            self,
            symbol: SupportedSymbol,
            timeframe: str,
            start: datetime,
            end: datetime,
        ) -> list[Candle]:
            del symbol, timeframe, start, end
            self.read_active = True
            self.read_active = False
            return []

        async def upsert_complete(self, candles: list[Candle]) -> None:
            del candles

    repository = TrackingRepository()

    class AssertingProvider(FakeProvider):
        async def fetch_candles(
            self,
            symbol: SupportedSymbol,
            timeframe: str,
            provider_interval: str,
            start: datetime,
            end: datetime,
            limit: int,
        ) -> list[Candle]:
            assert repository.read_active is False
            return await super().fetch_candles(
                symbol,
                timeframe,
                provider_interval,
                start,
                end,
                limit,
            )

    app.dependency_overrides[get_candle_repository] = lambda: repository
    app.dependency_overrides[get_candle_provider] = lambda: AssertingProvider()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/v1/candles",
                params={
                    "symbol": "BTC/USD",
                    "timeframe": "1m",
                    "from": "2026-06-19T00:00:00Z",
                    "to": "2026-06-19T00:01:00Z",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


async def test_stream_manager_persists_completed_candles_but_not_forming(
    database_engine: AsyncEngine,
) -> None:
    class FakeStreamProvider:
        def __init__(self) -> None:
            self.events: asyncio.Queue[ProviderStreamEvent] = asyncio.Queue()

        async def subscribe_quote(self, symbol: SupportedSymbol) -> None:
            del symbol

        async def subscribe_candle(
            self,
            symbol: SupportedSymbol,
            timeframe: str,
            provider_interval: str,
        ) -> None:
            del symbol, timeframe, provider_interval

        async def unsubscribe(self, interest: object) -> None:
            del interest

        async def close(self) -> None:
            return

    provider = FakeStreamProvider()
    repository = PostgresCandleRepository(async_sessionmaker(database_engine))
    manager = StreamManager(
        provider=provider,
        quote_cache=QuoteCache(),
        candle_cache=CandleCache(),
        candle_repository=repository,
        client_queue_capacity=20,
        persistence_queue_capacity=20,
        idle_grace_seconds=0,
        stale_after_seconds=30,
        freshness_check_seconds=3600,
    )
    try:
        await manager.register(StreamRequest(("BTC/USD",), "1m"), [BTC])
        forming = make_candle(START)
        completed = replace(make_candle(START + timedelta(minutes=1)), complete=True)

        await provider.events.put(StreamCandle(forming, START))
        await provider.events.put(StreamCandle(completed, START + timedelta(minutes=1)))
        await asyncio.wait_for(manager._persistence_queue.join(), timeout=1)  # noqa: SLF001
    finally:
        await manager.stop()

    rows = await repository.list_complete(
        BTC,
        "1m",
        START,
        START + timedelta(minutes=2),
    )

    assert [row.open_time for row in rows] == [START + timedelta(minutes=1)]
