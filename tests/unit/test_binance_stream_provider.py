from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from app.domain.errors import ProviderUnavailableError
from app.domain.streams import ProviderSignal, QuoteInterest, StreamQuote
from app.domain.symbols import SupportedSymbol
from app.providers.binance_spot_stream import BinanceSpotStreamProvider, BinanceWebSocketStreams

BTC = SupportedSymbol("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True, 2)
START = datetime(2026, 6, 19, 10, 30, tzinfo=UTC)


class FakeHandle:
    def __init__(self) -> None:
        self.callbacks: list[object] = []
        self.unsubscribed = False

    def on(self, event: str, callback: object) -> None:
        assert event == "message"
        self.callbacks.append(callback)

    async def unsubscribe(self) -> None:
        self.unsubscribed = True


class FakeStreams:
    def __init__(self, *, connect: bool = True, error: Exception | None = None) -> None:
        self.connections: list[object] = []
        self.connect = connect
        self.error = error
        self.ticker_symbols: list[str] = []
        self.kline_calls: list[object] = []
        self.ticker_handle = FakeHandle()
        self.closed = False

    async def create_connection(self) -> object:
        if self.error is not None:
            raise self.error
        if self.connect:
            self.connections.append(object())
        return self

    async def ticker(self, symbol: str) -> FakeHandle:
        self.ticker_symbols.append(symbol)
        return self.ticker_handle

    async def close_connection(self) -> None:
        self.closed = True
        self.connections.clear()


def ticker_payload(**overrides: object) -> SimpleNamespace:
    data = {"s": "BTCUSD", "E": int(START.timestamp() * 1000), "c": "63388.84000000"}
    data.update(overrides)
    return SimpleNamespace(**data)


async def test_stream_provider_is_ticker_only_and_normalizes_quotes() -> None:
    streams = FakeStreams()
    provider = BinanceSpotStreamProvider(cast(BinanceWebSocketStreams, streams), queue_capacity=10)

    await provider.subscribe_quote(BTC)
    streams.ticker_handle.callbacks[0](ticker_payload())

    quote = await provider.events.get()
    assert streams.ticker_symbols == ["btcusd"]
    assert streams.kline_calls == []
    assert isinstance(quote, StreamQuote)
    assert quote.quote.symbol == "BTC/USD"
    assert str(quote.quote.price) == "63388.84000000"
    assert quote.quote.provider_symbol == "BTCUSD"


@pytest.mark.parametrize(
    "payload",
    [
        ticker_payload(s="ETHUSD"),
        ticker_payload(E=-1),
        ticker_payload(c="NaN"),
    ],
)
async def test_stream_provider_rejects_malformed_ticker_payload(payload: object) -> None:
    streams = FakeStreams()
    provider = BinanceSpotStreamProvider(cast(BinanceWebSocketStreams, streams), queue_capacity=10)
    await provider.subscribe_quote(BTC)

    streams.ticker_handle.callbacks[0](payload)

    assert provider.events.empty()


async def test_stream_provider_maps_connection_failure_and_suppressed_connection() -> None:
    provider = BinanceSpotStreamProvider(
        cast(BinanceWebSocketStreams, FakeStreams(error=RuntimeError("boom"))),
        queue_capacity=10,
    )
    with pytest.raises(ProviderUnavailableError):
        await provider.subscribe_quote(BTC)

    provider = BinanceSpotStreamProvider(
        cast(BinanceWebSocketStreams, FakeStreams(connect=False)),
        queue_capacity=10,
    )
    with pytest.raises(ProviderUnavailableError):
        await provider.subscribe_quote(BTC)


async def test_stream_provider_unsubscribes_and_closes_connection() -> None:
    streams = FakeStreams()
    provider = BinanceSpotStreamProvider(cast(BinanceWebSocketStreams, streams), queue_capacity=10)
    await provider.subscribe_quote(BTC)

    await provider.unsubscribe(QuoteInterest("BTC/USD"))

    assert streams.ticker_handle.unsubscribed is True
    assert streams.closed is True


async def test_stream_provider_emits_quote_reconnecting_and_error_signals() -> None:
    streams = FakeStreams()
    provider = BinanceSpotStreamProvider(cast(BinanceWebSocketStreams, streams), queue_capacity=10)
    await provider.subscribe_quote(BTC)

    provider.emit_reconnecting()
    provider.emit_error()

    reconnecting = await provider.events.get()
    error = await provider.events.get()
    assert isinstance(reconnecting, ProviderSignal)
    assert reconnecting.state == "RECONNECTING"
    assert reconnecting.interests == (
        QuoteInterest("BTC/USD", "BINANCE_SPOT", "BTCUSD"),
    )
    assert isinstance(error, ProviderSignal)
    assert error.state == "ERROR"

