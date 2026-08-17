import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.cache.quote_cache import QuoteCache
from app.domain.quotes import Quote
from app.domain.streams import (
    ProviderSignal,
    ProviderStreamEvent,
    QuoteInterest,
    StatusEvent,
    StreamInterest,
    StreamQuote,
    StreamRequest,
)
from app.domain.symbols import SupportedSymbol
from app.services.stream_manager import StreamManager

BTC = SupportedSymbol("BTC/USD", "CRYPTO", "TWELVE_DATA", "BTC/USD", True, 2)
ETH = SupportedSymbol("ETH/USD", "CRYPTO", "TWELVE_DATA", "ETH/USD", True, 2)
BINANCE_BTC = SupportedSymbol("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True, 2)
SILVER = SupportedSymbol("XAG/USD", "COMMODITY", "YFINANCE", "SI=F", True, 3)
START = datetime(2026, 6, 19, 10, 30, tzinfo=UTC)


class FakeProvider:
    def __init__(self) -> None:
        self.events: asyncio.Queue[ProviderStreamEvent] = asyncio.Queue()
        self.quote_subscriptions: list[SupportedSymbol] = []
        self.unsubscribed: list[StreamInterest] = []
        self.closed = False

    async def subscribe_quote(self, symbol: SupportedSymbol) -> None:
        self.quote_subscriptions.append(symbol)

    async def unsubscribe(self, interest: StreamInterest) -> None:
        self.unsubscribed.append(interest)

    async def close(self) -> None:
        self.closed = True


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


def make_manager(
    provider: FakeProvider,
    quote_cache: QuoteCache | None = None,
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
        client_queue_capacity=client_queue_capacity,
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


async def test_manager_shares_upstream_interests_and_fans_out_quote_events(
    running_manager: tuple[StreamManager, FakeProvider],
) -> None:
    manager, provider = running_manager
    request = StreamRequest(("BTC/USD",))

    first = await manager.register(request, [BTC])
    second = await manager.register(request, [BTC])

    assert first.price_display_decimals == {"BTC/USD": 2}
    assert second.price_display_decimals == {"BTC/USD": 2}
    assert provider.quote_subscriptions == [BTC]
    assert (await next_event(first.queue)).state == "CONNECTING"
    assert (await next_event(second.queue)).state == "CONNECTING"

    await provider.events.put(make_quote())
    assert await next_event(first.queue) == make_quote()
    assert await next_event(second.queue) == make_quote()
    assert (await next_event(first.queue)).state == "SUBSCRIBED"
    assert (await next_event(second.queue)).state == "SUBSCRIBED"


async def test_manager_updates_quote_cache_before_fanout() -> None:
    provider = FakeProvider()
    quote_cache = QuoteCache()
    manager = make_manager(provider, quote_cache)
    try:
        registration = await manager.register(StreamRequest(("BTC/USD",)), [BTC])
        await next_event(registration.queue)

        quote = make_quote()
        await provider.events.put(quote)

        assert await next_event(registration.queue) == quote
        cached = await quote_cache.get_many([BTC])
        assert cached["BTC/USD"] == quote.quote
    finally:
        await manager.stop()


async def test_manager_does_not_send_an_initial_quote_snapshot() -> None:
    provider = FakeProvider()
    quote_cache = QuoteCache()
    await quote_cache.put_many([make_quote().quote])
    manager = make_manager(provider, quote_cache)
    try:
        registration = await manager.register(StreamRequest(("BTC/USD",)), [BTC])
        assert (await next_event(registration.queue)).state == "CONNECTING"
        await asyncio.sleep(0)
        assert registration.queue.empty()
    finally:
        await manager.stop()


async def test_manager_keeps_upstream_until_final_subscriber_disconnects() -> None:
    provider = FakeProvider()
    manager = make_manager(provider)
    first = await manager.register(StreamRequest(("BTC/USD",)), [BTC])
    second = await manager.register(StreamRequest(("BTC/USD",)), [BTC])
    await next_event(first.queue)
    await next_event(second.queue)

    await manager.unregister(first.id)
    await asyncio.sleep(0)
    assert provider.unsubscribed == []

    await manager.unregister(second.id)
    await asyncio.sleep(0.01)
    assert provider.unsubscribed == [QuoteInterest("BTC/USD", "TWELVE_DATA", "BTC/USD")]
    await manager.stop()


async def test_manager_cancels_idle_cleanup_when_new_subscriber_arrives() -> None:
    provider = FakeProvider()
    manager = make_manager(provider, idle_grace_seconds=0.02)
    try:
        first = await manager.register(StreamRequest(("BTC/USD",)), [BTC])
        await next_event(first.queue)
        await manager.unregister(first.id)
        await asyncio.sleep(0.005)

        second = await manager.register(StreamRequest(("BTC/USD",)), [BTC])
        await next_event(second.queue)
        await asyncio.sleep(0.03)

        assert provider.unsubscribed == []
        assert manager.active_interests == 1
    finally:
        await manager.stop()


async def test_manager_status_transitions_and_provider_signals() -> None:
    provider = FakeProvider()
    current = START
    manager = StreamManager(
        provider=provider,
        quote_cache=QuoteCache(),
        client_queue_capacity=20,
        idle_grace_seconds=0,
        stale_after_seconds=1,
        freshness_check_seconds=3600,
        clock=lambda: current,
    )
    try:
        registration = await manager.register(StreamRequest(("BTC/USD",)), [BTC])
        assert (await next_event(registration.queue)).state == "CONNECTING"

        await provider.events.put(make_quote(received_at=current))
        assert isinstance(await next_event(registration.queue), StreamQuote)
        subscribed = await next_event(registration.queue)
        assert isinstance(subscribed, StatusEvent)
        assert subscribed.state == "SUBSCRIBED"
        assert subscribed.channels == ("quote",)

        current = START + timedelta(seconds=2)
        manager._update_registration_state(registration, current)  # noqa: SLF001
        stale = await next_event(registration.queue)
        assert isinstance(stale, StatusEvent)
        assert stale.state == "STALE"
        assert stale.channels == ("quote",)

        await provider.events.put(
            ProviderSignal("RECONNECTING", registration.interests, current)
        )
        reconnecting = await next_event(registration.queue)
        assert isinstance(reconnecting, StatusEvent)
        assert reconnecting.state == "RECONNECTING"
        assert reconnecting.channels == ("quote",)

        await provider.events.put(make_quote(received_at=current))
        assert isinstance(await next_event(registration.queue), StreamQuote)
        recovered = await next_event(registration.queue)
        assert isinstance(recovered, StatusEvent)
        assert recovered.state == "SUBSCRIBED"

        await provider.events.put(ProviderSignal("ERROR", registration.interests, current))
        error = await next_event(registration.queue)
        assert isinstance(error, StatusEvent)
        assert error.state == "ERROR"
        assert error.code == "PROVIDER_UNAVAILABLE"
        assert registration.close_code == 1011
        assert registration.close_reason == "PROVIDER_UNAVAILABLE"
    finally:
        await manager.stop()


async def test_manager_isolates_provider_selection_interests() -> None:
    provider = FakeProvider()
    manager = make_manager(provider)
    try:
        first = await manager.register(StreamRequest(("BTC/USD",)), [BTC])
        second = await manager.register(StreamRequest(("BTC/USD",), "BINANCE_SPOT"), [BINANCE_BTC])
        await next_event(first.queue)
        await next_event(second.queue)

        assert provider.quote_subscriptions == [BTC, BINANCE_BTC]
        assert first.interests != second.interests
    finally:
        await manager.stop()


async def test_manager_closes_slow_client_without_affecting_others() -> None:
    provider = FakeProvider()
    manager = make_manager(provider, client_queue_capacity=1)
    try:
        slow = await manager.register(StreamRequest(("BTC/USD",)), [BTC])
        other = await manager.register(StreamRequest(("ETH/USD",)), [ETH])

        manager._enqueue(slow, make_quote())  # noqa: SLF001

        assert slow.closed.is_set()
        assert slow.close_code == 1013
        assert other.closed.is_set() is False
        assert manager.active_clients == 2
    finally:
        await manager.stop()


async def test_manager_shutdown_closes_provider_and_clients() -> None:
    provider = FakeProvider()
    manager = make_manager(provider)
    registration = await manager.register(StreamRequest(("BTC/USD",)), [BTC])

    await manager.stop()

    assert registration.closed.is_set()
    assert registration.close_code == 1012
    assert provider.closed is True

