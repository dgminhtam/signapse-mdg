import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.errors import ProviderUnavailableError
from app.domain.streams import (
    CandleInterest,
    ProviderSignal,
    QuoteInterest,
    StreamCandle,
    StreamQuote,
)
from app.domain.symbols import SupportedSymbol
from app.providers.yfinance_market_data_stream import (
    YFinanceMarketDataStreamProvider,
)

SILVER = SupportedSymbol("XAG/USD", "COMMODITY", "YFINANCE", "SI=F", True)
BRENT = SupportedSymbol("BRENT", "COMMODITY", "YFINANCE", "BZ=F", True)
UNSUPPORTED = SupportedSymbol("AAPL", "US_STOCK", "YFINANCE", "AAPL", True)
NOW = datetime(2026, 6, 23, 9, 0, 30, tzinfo=UTC)


class FakeWebSocket:
    def __init__(
        self,
        *,
        subscribe_error: Exception | None = None,
        listen_error: Exception | None = None,
        unsubscribe_error: Exception | None = None,
    ) -> None:
        self.subscribe_error = subscribe_error
        self.listen_error = listen_error
        self.unsubscribe_error = unsubscribe_error
        self.subscribed: list[str | list[str]] = []
        self.unsubscribed: list[str | list[str]] = []
        self.closed = False
        self.listen_started = asyncio.Event()
        self.listen_release = asyncio.Event()
        self.handler: Callable[[dict[str, object]], None] | None = None

    async def subscribe(self, symbols: str | list[str]) -> None:
        if self.subscribe_error is not None:
            raise self.subscribe_error
        self.subscribed.append(symbols)

    async def unsubscribe(self, symbols: str | list[str]) -> None:
        if self.unsubscribe_error is not None:
            raise self.unsubscribe_error
        self.unsubscribed.append(symbols)

    async def listen(
        self,
        message_handler: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.handler = message_handler
        self.listen_started.set()
        if self.listen_error is not None:
            raise self.listen_error
        await self.listen_release.wait()

    async def close(self) -> None:
        self.closed = True
        self.listen_release.set()

    def emit(self, payload: dict[str, object]) -> None:
        assert self.handler is not None
        self.handler(payload)


class FakeFactory:
    def __init__(self, *clients: FakeWebSocket) -> None:
        self.clients = list(clients)
        self.created: list[FakeWebSocket] = []

    def __call__(self) -> FakeWebSocket:
        client = self.clients.pop(0)
        self.created.append(client)
        return client


def make_provider(
    factory: FakeFactory,
    *,
    queue_capacity: int = 20,
    reconnect_delay_seconds: float = 0,
) -> YFinanceMarketDataStreamProvider:
    return YFinanceMarketDataStreamProvider(
        factory,
        queue_capacity=queue_capacity,
        reconnect_delay_seconds=reconnect_delay_seconds,
        clock=lambda: NOW,
    )


async def next_event(provider: YFinanceMarketDataStreamProvider) -> object:
    return await asyncio.wait_for(provider.events.get(), timeout=1)


async def test_provider_is_lazy_shares_symbols_and_releases_final_references() -> None:
    client = FakeWebSocket()
    factory = FakeFactory(client)
    provider = make_provider(factory)

    assert factory.created == []
    await provider.subscribe_quote(SILVER)
    await provider.subscribe_candle(SILVER, "1m", "1m")
    await provider.subscribe_quote(BRENT)

    assert factory.created == [client]
    assert client.subscribed == [["SI=F"], "BZ=F"]

    await provider.unsubscribe(CandleInterest("XAG/USD", "1m"))
    assert client.unsubscribed == []
    await provider.unsubscribe(QuoteInterest("XAG/USD"))
    assert client.unsubscribed == ["SI=F"]
    await provider.unsubscribe(QuoteInterest("BRENT"))

    assert client.unsubscribed == ["SI=F", "BZ=F"]
    assert client.closed is True


async def test_provider_idempotently_subscribes_and_unsubscribes() -> None:
    client = FakeWebSocket()
    provider = make_provider(FakeFactory(client))

    await provider.subscribe_quote(SILVER)
    await provider.subscribe_quote(SILVER)
    await provider.subscribe_candle(SILVER, "5m", "5m")
    await provider.subscribe_candle(SILVER, "5m", "5m")

    assert client.subscribed == [["SI=F"]]

    await provider.unsubscribe(CandleInterest("XAG/USD", "5m"))
    await provider.unsubscribe(CandleInterest("XAG/USD", "5m"))
    await provider.unsubscribe(QuoteInterest("XAG/USD"))
    await provider.unsubscribe(QuoteInterest("XAG/USD"))

    assert client.unsubscribed == ["SI=F"]


@pytest.mark.parametrize("time_value", [1782205200, "1782205200000"])
async def test_provider_normalizes_quote_price_and_provider_timestamp(
    time_value: int | str,
) -> None:
    client = FakeWebSocket()
    provider = make_provider(FakeFactory(client))
    await provider.subscribe_quote(SILVER)
    await client.listen_started.wait()

    client.emit({"id": "SI=F", "price": 63.125, "time": time_value})
    event = await next_event(provider)

    assert isinstance(event, StreamQuote)
    assert event.quote.symbol == "XAG/USD"
    assert event.quote.provider_symbol == "SI=F"
    assert event.quote.price == Decimal("63.125")
    assert event.quote.provider_time == datetime(2026, 6, 23, 9, 0, tzinfo=UTC)
    assert event.quote.received_at == NOW
    await provider.close()


async def test_provider_accepts_absent_provider_time() -> None:
    client = FakeWebSocket()
    provider = make_provider(FakeFactory(client))
    await provider.subscribe_quote(SILVER)
    await client.listen_started.wait()

    client.emit({"id": "SI=F", "price": "63.125"})
    event = await next_event(provider)

    assert isinstance(event, StreamQuote)
    assert event.quote.provider_time is None
    await provider.close()


async def test_provider_derives_zero_volume_candles_and_ignores_day_volume() -> None:
    client = FakeWebSocket()
    provider = make_provider(FakeFactory(client))
    await provider.subscribe_candle(SILVER, "1m", "1m")
    await client.listen_started.wait()

    client.emit(
        {
            "id": "SI=F",
            "price": "63.10",
            "time": int(datetime(2026, 6, 23, 9, 0, 10, tzinfo=UTC).timestamp() * 1000),
            "day_volume": "999999",
        }
    )
    first = await next_event(provider)
    client.emit(
        {
            "id": "SI=F",
            "price": "63.40",
            "time": int(datetime(2026, 6, 23, 9, 0, 50, tzinfo=UTC).timestamp() * 1000),
        }
    )
    updated = await next_event(provider)
    client.emit(
        {
            "id": "SI=F",
            "price": "63.20",
            "time": int(datetime(2026, 6, 23, 9, 5, 1, tzinfo=UTC).timestamp() * 1000),
        }
    )
    completed = await next_event(provider)
    later = await next_event(provider)

    assert isinstance(first, StreamCandle)
    assert first.candle.volume == Decimal("0")
    assert isinstance(updated, StreamCandle)
    assert updated.candle.high == Decimal("63.40")
    assert isinstance(completed, StreamCandle)
    assert completed.candle.complete is True
    assert completed.candle.open_time == datetime(2026, 6, 23, 9, 0, tzinfo=UTC)
    assert isinstance(later, StreamCandle)
    assert later.candle.open_time == datetime(2026, 6, 23, 9, 5, tzinfo=UTC)
    await provider.close()


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "UNKNOWN", "price": "1"},
        {"id": "SI=F", "price": True},
        {"id": "SI=F", "price": "nan"},
        {"id": "SI=F", "price": "0"},
        {"id": "SI=F", "price": "-1"},
        {"id": "SI=F", "price": "1", "time": "invalid"},
        {"price": "1"},
    ],
)
async def test_provider_rejects_malformed_unknown_or_inactive_payloads(
    payload: dict[str, object],
) -> None:
    client = FakeWebSocket()
    provider = make_provider(FakeFactory(client))
    await provider.subscribe_quote(SILVER)
    await client.listen_started.wait()

    client.emit(payload)
    await asyncio.sleep(0)

    assert provider.events.empty()
    await provider.close()


async def test_provider_drops_events_when_provider_queue_is_full() -> None:
    client = FakeWebSocket()
    provider = make_provider(FakeFactory(client), queue_capacity=1)
    await provider.subscribe_quote(SILVER)
    await client.listen_started.wait()

    client.emit({"id": "SI=F", "price": "63.1"})
    client.emit({"id": "SI=F", "price": "63.2"})

    event = await next_event(provider)
    assert isinstance(event, StreamQuote)
    assert event.quote.price == Decimal("63.1")
    await provider.close()


async def test_successful_silent_subscription_emits_nothing() -> None:
    client = FakeWebSocket()
    provider = make_provider(FakeFactory(client))

    await provider.subscribe_quote(SILVER)
    await provider.subscribe_candle(SILVER, "1m", "1m")
    await client.listen_started.wait()
    await asyncio.sleep(0)

    assert provider.events.empty()
    await provider.close()


async def test_listener_failure_emits_reconnecting_and_recreates_client() -> None:
    first = FakeWebSocket(listen_error=RuntimeError("connection lost"))
    second = FakeWebSocket()
    provider = make_provider(FakeFactory(first, second))
    await provider.subscribe_quote(SILVER)

    signal = await next_event(provider)
    await asyncio.wait_for(second.listen_started.wait(), timeout=1)

    assert isinstance(signal, ProviderSignal)
    assert signal.state == "RECONNECTING"
    assert signal.interests == (QuoteInterest("XAG/USD"),)
    assert first.closed is True
    assert second.subscribed == [["SI=F"]]
    await provider.close()
    assert second.closed is True


async def test_unsubscribe_failure_is_isolated_and_close_is_deterministic() -> None:
    client = FakeWebSocket(unsubscribe_error=RuntimeError("unsubscribe failed"))
    provider = make_provider(FakeFactory(client))
    await provider.subscribe_quote(SILVER)
    await client.listen_started.wait()

    await provider.unsubscribe(QuoteInterest("XAG/USD"))

    assert client.closed is True
    assert provider.events.empty()


async def test_initial_subscribe_failure_is_sanitized_and_closes_client() -> None:
    client = FakeWebSocket(subscribe_error=RuntimeError("secret upstream detail"))
    provider = make_provider(FakeFactory(client))

    with pytest.raises(ProviderUnavailableError):
        await provider.subscribe_quote(SILVER)

    assert client.closed is True
    assert provider.events.empty()


async def test_provider_rejects_unsupported_symbol_and_timeframe_without_client() -> None:
    factory = FakeFactory(FakeWebSocket())
    provider = make_provider(factory)

    with pytest.raises(ProviderUnavailableError):
        await provider.subscribe_quote(UNSUPPORTED)
    with pytest.raises(ProviderUnavailableError):
        await provider.subscribe_candle(SILVER, "2m", "2m")

    assert factory.created == []
