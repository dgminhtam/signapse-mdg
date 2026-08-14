import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.cache.candle_cache import CandleCache
from app.cache.quote_cache import QuoteCache
from app.db.repositories import PostgresSymbolRepository
from app.domain.candles import Candle, CandleRequest
from app.domain.quotes import ProviderQuoteBatch, Quote
from app.domain.streams import (
    CandleInterest,
    ProviderStreamEvent,
    QuoteInterest,
    StreamCandle,
    StreamQuote,
    StreamRequest,
)
from app.domain.symbols import ProviderMapping, SupportedSymbol
from app.domain.timeframes import TIMEFRAMES, candle_close_time, get_timeframe
from app.services.candles import CandleService
from app.services.historical_prices import HistoricalPriceRequest, HistoricalPriceService
from app.services.provider_selection import resolve_provider_selection
from app.services.quotes import QuoteService
from app.services.stream_manager import StreamManager
from app.services.stream_provider_router import MultiProviderStreamProvider

pytestmark = pytest.mark.integration

MATRIX_START = datetime(2026, 7, 27, 14, 0, tzinfo=UTC)
MATRIX_AT = datetime(2026, 7, 27, 14, 30, 30, tzinfo=UTC)
MATRIX_NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)


class RegistryRepository:
    def __init__(self, symbols: list[SupportedSymbol]) -> None:
        self._symbols = {symbol.symbol: symbol for symbol in symbols}
        self.upserted: list[Candle] = []

    async def list_enabled(self) -> list[SupportedSymbol]:
        return list(self._symbols.values())

    async def get_enabled_symbol(self, symbol: str) -> SupportedSymbol | None:
        return self._symbols.get(symbol)

    async def list_complete(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        del symbol, timeframe, start, end
        return []

    async def upsert_complete(self, candles: list[Candle]) -> None:
        self.upserted.extend(candles)


class MatrixQuoteProvider:
    def __init__(self) -> None:
        self.calls: list[SupportedSymbol] = []

    async def fetch_latest_prices(
        self,
        symbols: list[SupportedSymbol],
    ) -> ProviderQuoteBatch:
        self.calls.extend(symbols)
        return ProviderQuoteBatch(
            prices={symbol.provider_symbol: Decimal("100.00") for symbol in symbols},
            unavailable_symbols=frozenset(),
        )


class MatrixCandleProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[SupportedSymbol, str]] = []

    async def fetch_candles(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[Candle]:
        del provider_interval, end, limit
        self.calls.append((symbol, timeframe))
        timeframe_model = get_timeframe(timeframe)
        assert timeframe_model is not None
        return [
            Candle(
                symbol=symbol.symbol,
                asset_class=symbol.asset_class,
                provider=symbol.provider,
                provider_symbol=symbol.provider_symbol,
                timeframe=timeframe,
                open_time=start,
                close_time=candle_close_time(start, timeframe_model),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100.50"),
                volume=Decimal("1"),
                complete=True,
            )
        ]


class MatrixStreamProvider:
    def __init__(self) -> None:
        self.events: asyncio.Queue[ProviderStreamEvent] = asyncio.Queue()
        self.quote_subscriptions: list[SupportedSymbol] = []
        self.candle_subscriptions: list[tuple[SupportedSymbol, str]] = []

    async def subscribe_quote(self, symbol: SupportedSymbol) -> None:
        self.quote_subscriptions.append(symbol)

    async def subscribe_candle(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
    ) -> None:
        del provider_interval
        self.candle_subscriptions.append((symbol, timeframe))

    async def unsubscribe(self, interest: QuoteInterest | CandleInterest) -> None:
        del interest

    async def close(self) -> None:
        return None


async def _registry_symbols(database_engine: AsyncEngine) -> list[SupportedSymbol]:
    session_factory = async_sessionmaker(database_engine, expire_on_commit=False)
    async with session_factory() as session:
        return await PostgresSymbolRepository(session).list_enabled()


def _mapping_cases(
    symbols: Iterable[SupportedSymbol],
) -> list[tuple[SupportedSymbol, ProviderMapping]]:
    cases: list[tuple[SupportedSymbol, ProviderMapping]] = []
    for symbol in symbols:
        cases.extend((symbol, mapping) for mapping in symbol.mappings)
    return cases


async def _next_stream_event(
    registration_queue: asyncio.Queue[object],
    event_type: type[StreamQuote] | type[StreamCandle],
) -> StreamQuote | StreamCandle:
    while True:
        event = await asyncio.wait_for(registration_queue.get(), timeout=1)
        if isinstance(event, event_type):
            return event


async def test_every_registry_mapping_passes_market_data_surface_smoke_matrix(
    database_engine: AsyncEngine,
) -> None:
    symbols = await _registry_symbols(database_engine)
    cases = _mapping_cases(symbols)
    assert len(symbols) == 24
    assert len(cases) == 29

    symbol_repository = RegistryRepository(symbols)
    quote_provider = MatrixQuoteProvider()
    quote_service = QuoteService(
        symbol_repository,
        quote_provider,
        QuoteCache(),
        cache_ttl_seconds=60,
        stale_after_seconds=120,
        clock=lambda: MATRIX_NOW,
    )
    candle_provider = MatrixCandleProvider()
    candle_service = CandleService(
        symbol_repository,
        candle_provider,
        CandleCache(),
        clock=lambda: MATRIX_NOW,
    )
    historical_service = HistoricalPriceService(candle_service)

    for symbol, mapping in cases:
        selected, selection = resolve_provider_selection(symbol, mapping.provider)
        assert selected.provider_symbol == mapping.provider_symbol
        assert selection.provider == mapping.provider

        quotes = await quote_service.get_latest_quotes([symbol.symbol], mapping.provider)
        assert len(quotes.quotes) == 1
        assert not quotes.errors
        assert quotes.quotes[0].provider == mapping.provider
        assert quotes.quotes[0].provider_symbol == mapping.provider_symbol

        for timeframe in TIMEFRAMES:
            start = (
                datetime(2026, 7, 1, tzinfo=UTC)
                if timeframe == "1mo"
                else MATRIX_START
            )
            result = await candle_service.get_candles(
                CandleRequest(
                    symbol.symbol,
                    timeframe,
                    start,
                    start,
                    limit=1,
                    count_direction="forward",
                    provider=mapping.provider,
                )
            )
            assert result.candles
            assert all(
                candle.provider == mapping.provider
                and candle.provider_symbol == mapping.provider_symbol
                for candle in result.candles
            )

        historical = await historical_service.get_historical_price(
            HistoricalPriceRequest(symbol.symbol, MATRIX_AT, mapping.provider)
        )
        assert historical.symbol == symbol.symbol
        assert historical.priced_at <= MATRIX_AT
        assert any(
            candidate.provider == mapping.provider
            and candidate.provider_symbol == mapping.provider_symbol
            for candidate in symbol_repository.upserted
            if candidate.symbol == symbol.symbol
        )

    stream_children = {
        provider: MatrixStreamProvider()
        for provider in {mapping.provider for _, mapping in cases}
    }
    stream_provider = MultiProviderStreamProvider(stream_children, queue_capacity=128)
    manager = StreamManager(
        provider=stream_provider,
        quote_cache=QuoteCache(),
        candle_cache=CandleCache(),
        candle_repository=None,
        client_queue_capacity=20,
        persistence_queue_capacity=20,
        idle_grace_seconds=0,
        stale_after_seconds=60,
        freshness_check_seconds=3600,
        clock=lambda: MATRIX_NOW,
    )
    try:
        for symbol, mapping in cases:
            selected, _selection = resolve_provider_selection(symbol, mapping.provider)
            registration = await manager.register(
                StreamRequest((symbol.symbol,), "1m", mapping.provider),
                [selected],
            )
            child = stream_children[mapping.provider]
            quote = StreamQuote(
                quote=Quote(
                    symbol=symbol.symbol,
                    asset_class=symbol.asset_class,
                    provider=mapping.provider,
                    provider_symbol=mapping.provider_symbol,
                    price=Decimal("100"),
                    volume=None,
                    provider_time=None,
                    received_at=MATRIX_NOW,
                )
            )
            timeframe_model = get_timeframe("1m")
            assert timeframe_model is not None
            candle = StreamCandle(
                candle=Candle(
                    symbol=symbol.symbol,
                    asset_class=symbol.asset_class,
                    provider=mapping.provider,
                    provider_symbol=mapping.provider_symbol,
                    timeframe="1m",
                    open_time=MATRIX_START,
                    close_time=candle_close_time(MATRIX_START, timeframe_model),
                    open=Decimal("100"),
                    high=Decimal("101"),
                    low=Decimal("99"),
                    close=Decimal("100.50"),
                    volume=Decimal("1"),
                    complete=False,
                ),
                received_at=MATRIX_NOW,
            )
            await child.events.put(quote)
            await child.events.put(candle)
            assert await _next_stream_event(registration.queue, StreamQuote) == quote
            assert await _next_stream_event(registration.queue, StreamCandle) == candle
            assert child.quote_subscriptions[-1] == selected
            assert child.candle_subscriptions[-1] == (selected, "1m")
            await manager.unregister(registration.id)
            await asyncio.sleep(0)
    finally:
        await manager.stop()
