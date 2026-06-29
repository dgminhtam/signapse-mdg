import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.cache.candle_cache import CandleCache
from app.cache.quote_cache import QuoteCache
from app.domain.candles import Candle
from app.domain.quotes import Quote
from app.domain.streams import (
    CandleInterest,
    ProviderSignal,
    ProviderStreamEvent,
    QuoteInterest,
    StatusEvent,
    StreamCandle,
    StreamInterest,
    StreamQuote,
    StreamRequest,
)
from app.domain.symbols import SupportedSymbol
from app.services.stream_manager import StreamManager

BTC = SupportedSymbol("BTC/USD", "CRYPTO", "TWELVE_DATA", "BTC/USD", True)
ETH = SupportedSymbol("ETH/USD", "CRYPTO", "TWELVE_DATA", "ETH/USD", True)
EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True)
SPY = SupportedSymbol("SPY", "ETF", "TWELVE_DATA", "SPY", True)
WTI = SupportedSymbol("WTI", "COMMODITY", "TWELVE_DATA", "WTI", True)
SILVER = SupportedSymbol("XAG/USD", "COMMODITY", "YFINANCE", "SI=F", True)
START = datetime(2026, 6, 19, 10, 30, tzinfo=UTC)


class FakeProvider:
    def __init__(self) -> None:
        self.events: asyncio.Queue[ProviderStreamEvent] = asyncio.Queue()
        self.quote_subscriptions: list[str] = []
        self.candle_subscriptions: list[tuple[str, str, str]] = []
        self.unsubscribed: list[StreamInterest] = []
        self.closed = False

    async def subscribe_quote(self, symbol: SupportedSymbol) -> None:
        self.quote_subscriptions.append(symbol.symbol)

    async def subscribe_candle(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
    ) -> None:
        self.candle_subscriptions.append((symbol.symbol, timeframe, provider_interval))

    async def unsubscribe(self, interest: StreamInterest) -> None:
        self.unsubscribed.append(interest)

    async def close(self) -> None:
        self.closed = True


class FakeRepository:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.upserted: list[Candle] = []

    async def upsert_complete(self, candles: list[Candle]) -> None:
        if self.fail:
            raise RuntimeError("database down")
        self.upserted.extend(candles)


def make_quote(symbol: SupportedSymbol = BTC, received_at: datetime = START) -> StreamQuote:
    return StreamQuote(
        Quote(
            symbol.symbol,
            symbol.asset_class,
            symbol.provider,
            symbol.provider_symbol,
            Decimal("10.00"),
            None,
            None,
            received_at,
        )
    )


def make_candle(
    symbol: SupportedSymbol = BTC,
    *,
    complete: bool = False,
    timeframe: str = "1m",
    open_time: datetime = START,
    received_at: datetime = START,
) -> StreamCandle:
    return StreamCandle(
        Candle(
            symbol.symbol,
            symbol.asset_class,
            symbol.provider,
            symbol.provider_symbol,
            timeframe,
            open_time,
            open_time + timedelta(minutes=1) - timedelta(milliseconds=1),
            Decimal("10"),
            Decimal("11"),
            Decimal("9"),
            Decimal("10.5"),
            Decimal("1"),
            complete,
        ),
        received_at,
    )


def make_manager(
    provider: FakeProvider,
    quote_cache: QuoteCache | None = None,
    candle_cache: CandleCache | None = None,
    repository: FakeRepository | None = None,
    *,
    client_queue_capacity: int = 20,
    idle_grace_seconds: float = 0,
    stale_after_seconds: float = 30,
    freshness_check_seconds: float = 3600,
    now: datetime = START,
) -> StreamManager:
    return StreamManager(
        provider=provider,
        quote_cache=quote_cache or QuoteCache(),
        candle_cache=candle_cache or CandleCache(),
        candle_repository=repository,
        client_queue_capacity=client_queue_capacity,
        persistence_queue_capacity=20,
        idle_grace_seconds=idle_grace_seconds,
        stale_after_seconds=stale_after_seconds,
        freshness_check_seconds=freshness_check_seconds,
        clock=lambda: now,
    )


@pytest.fixture
async def running_manager() -> AsyncIterator[tuple[StreamManager, FakeProvider]]:
    provider = FakeProvider()
    manager = make_manager(provider)
    try:
        yield manager, provider
    finally:
        await manager.stop()


async def next_event(queue: asyncio.Queue[object]) -> object:
    return await asyncio.wait_for(queue.get(), timeout=1)


async def test_manager_shares_upstream_interests_and_fans_out_events(
    running_manager: tuple[StreamManager, FakeProvider],
) -> None:
    manager, provider = running_manager
    request = StreamRequest(("BTC/USD",), "1m")

    first = await manager.register(request, [BTC])
    second = await manager.register(request, [BTC])

    assert provider.quote_subscriptions == ["BTC/USD"]
    assert provider.candle_subscriptions == [("BTC/USD", "1m", "1m")]
    assert isinstance(await next_event(first.queue), StatusEvent)
    assert isinstance(await next_event(second.queue), StatusEvent)

    await provider.events.put(make_quote())
    assert isinstance(await next_event(first.queue), StreamQuote)
    assert isinstance(await next_event(second.queue), StreamQuote)


async def test_manager_keeps_upstream_until_final_subscriber_disconnects(
    running_manager: tuple[StreamManager, FakeProvider],
) -> None:
    manager, provider = running_manager
    first = await manager.register(StreamRequest(("BTC/USD",), "1m"), [BTC])
    second = await manager.register(StreamRequest(("BTC/USD",), "1m"), [BTC])

    await manager.unregister(first.id)
    await asyncio.sleep(0)
    assert provider.unsubscribed == []

    await manager.unregister(second.id)
    await asyncio.sleep(0.01)
    assert set(provider.unsubscribed) == {QuoteInterest("BTC/USD"), CandleInterest("BTC/USD", "1m")}


async def test_manager_cancels_idle_cleanup_when_new_subscriber_arrives() -> None:
    provider = FakeProvider()
    manager = make_manager(provider, idle_grace_seconds=0.05)
    try:
        first = await manager.register(StreamRequest(("BTC/USD",), "1m"), [BTC])
        await manager.unregister(first.id)
        await manager.register(StreamRequest(("BTC/USD",), "1m"), [BTC])
        await asyncio.sleep(0.07)
        assert provider.unsubscribed == []
    finally:
        await manager.stop()


async def test_manager_updates_quote_and_candle_caches_before_fanout() -> None:
    provider = FakeProvider()
    quote_cache = QuoteCache()
    candle_cache = CandleCache()
    manager = make_manager(provider, quote_cache=quote_cache, candle_cache=candle_cache)
    try:
        registration = await manager.register(StreamRequest(("BTC/USD",), "1m"), [BTC])
        await next_event(registration.queue)

        quote = make_quote()
        candle = make_candle()
        await provider.events.put(quote)
        await provider.events.put(candle)
        await next_event(registration.queue)
        await next_event(registration.queue)

        assert (await quote_cache.get_many(["BTC/USD"]))["BTC/USD"] == quote.quote
        assert await candle_cache.get("BTC/USD", "1m") == candle.candle
    finally:
        await manager.stop()


async def test_manager_persists_completed_candles_without_blocking_fanout() -> None:
    provider = FakeProvider()
    candle_cache = CandleCache()
    repository = FakeRepository()
    manager = make_manager(provider, candle_cache=candle_cache, repository=repository)
    try:
        registration = await manager.register(StreamRequest(("BTC/USD",), "1m"), [BTC])
        await next_event(registration.queue)
        forming = make_candle()
        await candle_cache.put(forming.candle)
        completed = make_candle(complete=True)

        await provider.events.put(completed)
        assert await next_event(registration.queue) == completed
        await asyncio.wait_for(manager._persistence_queue.join(), timeout=1)  # noqa: SLF001

        assert await candle_cache.get("BTC/USD", "1m") is None
        assert repository.upserted == [completed.candle]
    finally:
        await manager.stop()


async def test_manager_isolates_persistence_failure_from_live_fanout() -> None:
    provider = FakeProvider()
    manager = make_manager(provider, repository=FakeRepository(fail=True))
    try:
        registration = await manager.register(StreamRequest(("BTC/USD",), "1m"), [BTC])
        await next_event(registration.queue)
        completed = make_candle(complete=True)

        await provider.events.put(completed)

        assert await next_event(registration.queue) == completed
    finally:
        await manager.stop()


async def test_manager_status_transitions_and_provider_signals() -> None:
    provider = FakeProvider()
    current = START
    manager = StreamManager(
        provider=provider,
        quote_cache=QuoteCache(),
        candle_cache=CandleCache(),
        candle_repository=None,
        client_queue_capacity=20,
        persistence_queue_capacity=20,
        idle_grace_seconds=0,
        stale_after_seconds=1,
        freshness_check_seconds=3600,
        clock=lambda: current,
    )
    try:
        registration = await manager.register(StreamRequest(("BTC/USD",), "1m"), [BTC])
        connecting = await next_event(registration.queue)
        assert isinstance(connecting, StatusEvent)
        assert connecting.state == "CONNECTING"

        await provider.events.put(make_quote(received_at=current))
        await provider.events.put(make_candle(received_at=current))
        await next_event(registration.queue)
        await next_event(registration.queue)
        subscribed = await next_event(registration.queue)
        assert isinstance(subscribed, StatusEvent)
        assert subscribed.state == "SUBSCRIBED"

        current = START + timedelta(seconds=2)
        manager._update_registration_state(registration, current)  # noqa: SLF001
        stale = await next_event(registration.queue)
        assert isinstance(stale, StatusEvent)
        assert stale.state == "STALE"
        assert set(stale.channels) == {"quote", "candle"}

        await provider.events.put(ProviderSignal("RECONNECTING", registration.interests, current))
        reconnecting = await next_event(registration.queue)
        assert isinstance(reconnecting, StatusEvent)
        assert reconnecting.state == "RECONNECTING"

        await provider.events.put(ProviderSignal("ERROR", registration.interests, current))
        error = await next_event(registration.queue)
        assert isinstance(error, StatusEvent)
        assert error.state == "ERROR"
        assert registration.close_code == 1011
    finally:
        await manager.stop()


async def test_manager_keeps_silent_yfinance_subscription_connecting() -> None:
    provider = FakeProvider()
    manager = make_manager(provider)
    try:
        registration = await manager.register(
            StreamRequest(("XAG/USD",), "1m"),
            [SILVER],
        )

        connecting = await next_event(registration.queue)
        assert isinstance(connecting, StatusEvent)
        assert connecting.state == "CONNECTING"
        await asyncio.sleep(0)
        assert registration.queue.empty()
        assert provider.quote_subscriptions == ["XAG/USD"]
        assert provider.candle_subscriptions == [("XAG/USD", "1m", "1m")]
    finally:
        await manager.stop()


async def test_manager_marks_closed_forex_candles_without_stale_and_reopens() -> None:
    provider = FakeProvider()
    current = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    manager = StreamManager(
        provider=provider,
        quote_cache=QuoteCache(),
        candle_cache=CandleCache(),
        candle_repository=None,
        client_queue_capacity=20,
        persistence_queue_capacity=20,
        idle_grace_seconds=0,
        stale_after_seconds=1,
        freshness_check_seconds=3600,
        clock=lambda: current,
    )
    try:
        registration = await manager.register(StreamRequest(("EUR/USD",), "1h"), [EUR])
        connecting = await next_event(registration.queue)
        closed = await next_event(registration.queue)
        assert isinstance(connecting, StatusEvent)
        assert connecting.state == "CONNECTING"
        assert isinstance(closed, StatusEvent)
        assert closed.state == "MARKET_CLOSED"
        assert closed.channels == ("candle",)

        current = datetime(2026, 6, 20, 12, 2, tzinfo=UTC)
        manager._update_registration_state(registration, current)  # noqa: SLF001
        assert registration.queue.empty()

        current = datetime(2026, 6, 22, 0, 0, tzinfo=UTC)
        manager._update_market_session_states(current)  # noqa: SLF001
        reopened = await next_event(registration.queue)
        assert isinstance(reopened, StatusEvent)
        assert reopened.state == "CONNECTING"
        assert reopened.channels == ("candle",)
    finally:
        await manager.stop()


async def test_manager_filters_ineligible_forex_stream_candles_from_cache_and_persistence() -> None:
    provider = FakeProvider()
    candle_cache = CandleCache()
    repository = FakeRepository()
    manager = make_manager(
        provider,
        candle_cache=candle_cache,
        repository=repository,
        now=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
    )
    try:
        registration = await manager.register(StreamRequest(("EUR/USD",), "1h"), [EUR])
        await next_event(registration.queue)
        await next_event(registration.queue)

        forming = make_candle(
            EUR,
            timeframe="1h",
            open_time=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
        )
        completed = make_candle(
            EUR,
            complete=True,
            timeframe="1h",
            open_time=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
        )
        await provider.events.put(forming)
        await provider.events.put(completed)
        await asyncio.sleep(0.01)

        assert await candle_cache.get("EUR/USD", "1h") is None
        assert repository.upserted == []
        assert registration.queue.empty()
    finally:
        await manager.stop()


@pytest.mark.parametrize(
    ("symbol", "closed_time", "open_time"),
    [
        (
            SPY,
            datetime(2026, 6, 22, 12, 0, tzinfo=UTC),
            datetime(2026, 6, 22, 14, 0, tzinfo=UTC),
        ),
        (
            WTI,
            datetime(2026, 6, 22, 21, 0, tzinfo=UTC),
            datetime(2026, 6, 22, 22, 0, tzinfo=UTC),
        ),
    ],
)
async def test_manager_marks_new_asset_candle_sessions_closed_and_reopens(
    symbol: SupportedSymbol,
    closed_time: datetime,
    open_time: datetime,
) -> None:
    provider = FakeProvider()
    current = closed_time
    manager = StreamManager(
        provider=provider,
        quote_cache=QuoteCache(),
        candle_cache=CandleCache(),
        candle_repository=None,
        client_queue_capacity=20,
        persistence_queue_capacity=20,
        idle_grace_seconds=0,
        stale_after_seconds=1,
        freshness_check_seconds=3600,
        clock=lambda: current,
    )
    try:
        registration = await manager.register(
            StreamRequest((symbol.symbol,), "1h"),
            [symbol],
        )
        assert (await next_event(registration.queue)).state == "CONNECTING"
        closed = await next_event(registration.queue)
        assert isinstance(closed, StatusEvent)
        assert closed.state == "MARKET_CLOSED"
        assert closed.channels == ("candle",)

        current = open_time
        manager._update_market_session_states(current)  # noqa: SLF001
        reopened = await next_event(registration.queue)
        assert isinstance(reopened, StatusEvent)
        assert reopened.state == "CONNECTING"
        assert reopened.channels == ("candle",)
    finally:
        await manager.stop()


@pytest.mark.parametrize(
    ("symbol", "closed_time"),
    [
        (SPY, datetime(2026, 6, 22, 12, 0, tzinfo=UTC)),
        (WTI, datetime(2026, 6, 22, 21, 0, tzinfo=UTC)),
    ],
)
async def test_manager_filters_closed_wti_and_etf_stream_candles(
    symbol: SupportedSymbol,
    closed_time: datetime,
) -> None:
    provider = FakeProvider()
    candle_cache = CandleCache()
    repository = FakeRepository()
    manager = make_manager(
        provider,
        candle_cache=candle_cache,
        repository=repository,
        now=closed_time,
    )
    try:
        registration = await manager.register(
            StreamRequest((symbol.symbol,), "1h"),
            [symbol],
        )
        await next_event(registration.queue)
        await next_event(registration.queue)

        await provider.events.put(make_candle(symbol, timeframe="1h", open_time=closed_time))
        await provider.events.put(
            make_candle(
                symbol,
                complete=True,
                timeframe="1h",
                open_time=closed_time,
            )
        )
        await asyncio.sleep(0.01)

        assert await candle_cache.get(symbol.symbol, "1h") is None
        assert repository.upserted == []
        assert registration.queue.empty()
    finally:
        await manager.stop()


async def test_manager_closes_slow_client_without_affecting_others() -> None:
    provider = FakeProvider()
    manager = make_manager(provider, client_queue_capacity=1)
    try:
        slow = await manager.register(StreamRequest(("BTC/USD",), "1m"), [BTC])
        await manager.register(StreamRequest(("ETH/USD",), "1m"), [ETH])

        manager._enqueue(slow, make_quote())  # noqa: SLF001
        manager._enqueue(slow, make_quote())  # noqa: SLF001

        assert slow.closed.is_set()
        assert slow.close_code == 1013
        assert manager.active_clients == 2
    finally:
        await manager.stop()


async def test_manager_shutdown_closes_provider_and_clients() -> None:
    provider = FakeProvider()
    manager = make_manager(provider)
    registration = await manager.register(StreamRequest(("BTC/USD",), "1m"), [BTC])

    await manager.stop()

    assert registration.closed.is_set()
    assert registration.close_code == 1012
    assert provider.closed is True
