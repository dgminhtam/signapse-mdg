import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.streams import ProviderSignal, QuoteInterest, StreamQuote
from app.domain.symbols import SupportedSymbol
from app.providers import twelvedata_market_data_stream as stream_module
from app.providers.twelvedata_market_data_stream import (
    TwelveDataMarketDataStreamProvider,
    build_twelvedata_market_data_stream_provider,
)

BTC = SupportedSymbol("BTC/USD", "CRYPTO", "TWELVE_DATA", "BTC/USD", True, 2)
ETH = SupportedSymbol("ETH/USD", "CRYPTO", "TWELVE_DATA", "ETH/USD", True, 2)
EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True, 5)
WTI = SupportedSymbol("WTI", "COMMODITY", "TWELVE_DATA", "WTI", True, 2)
SPY = SupportedSymbol("SPY", "ETF", "TWELVE_DATA", "SPY", True, 2)
QQQ = SupportedSymbol("QQQ", "ETF", "TWELVE_DATA", "QQQ", True, 2)
START = datetime(2026, 6, 22, 0, 0, 10, tzinfo=UTC)


class FakeWebSocket:
    def __init__(self) -> None:
        self.connected = False
        self.disconnected = False
        self.subscribed: list[str] = []
        self.unsubscribed: list[str] = []
        self.heartbeats = 0

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.disconnected = True

    def subscribe(self, symbols: str | list[str]) -> None:
        self.subscribed.extend([symbols] if isinstance(symbols, str) else symbols)

    def unsubscribe(self, symbols: str | list[str]) -> None:
        self.unsubscribed.extend([symbols] if isinstance(symbols, str) else symbols)

    def heartbeat(self) -> None:
        self.heartbeats += 1


class FakeClient:
    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket_instance = websocket
        self.websocket_calls = 0
        self.on_event: Callable[[object], None] | None = None

    def websocket(self, **defaults: object) -> FakeWebSocket:
        self.websocket_calls += 1
        on_event = defaults.get("on_event")
        assert callable(on_event)
        self.on_event = on_event
        return self.websocket_instance


async def next_event(queue: asyncio.Queue[object]) -> object:
    return await asyncio.wait_for(queue.get(), timeout=1)


async def test_provider_lazily_connects_reuses_connection_and_cleans_up() -> None:
    websocket = FakeWebSocket()
    client = FakeClient(websocket)
    provider = TwelveDataMarketDataStreamProvider(
        lambda _: client,
        queue_capacity=10,
        heartbeat_seconds=60,
    )

    await provider.subscribe_quote(EUR)
    await provider.subscribe_quote(BTC)

    assert not hasattr(provider, "subscribe_candle")
    assert websocket.connected is True
    assert client.websocket_calls == 1
    assert websocket.subscribed == ["EUR/USD", "BTC/USD"]

    await provider.unsubscribe(QuoteInterest("EUR/USD", "TWELVE_DATA", "EUR/USD"))
    assert websocket.unsubscribed == ["EUR/USD"]
    await provider.close()
    assert websocket.disconnected is True


async def test_provider_reuses_connection_across_crypto_forex_wti_and_etfs() -> None:
    websocket = FakeWebSocket()
    client = FakeClient(websocket)
    provider = TwelveDataMarketDataStreamProvider(
        lambda _: client,
        queue_capacity=10,
        heartbeat_seconds=60,
    )

    for symbol in (BTC, ETH, EUR, WTI, SPY, QQQ):
        await provider.subscribe_quote(symbol)

    assert client.websocket_calls == 1
    assert websocket.subscribed == ["BTC/USD", "ETH/USD", "EUR/USD", "WTI", "SPY", "QQQ"]
    await provider.close()


async def test_provider_bridges_valid_price_payload_to_quote_only() -> None:
    websocket = FakeWebSocket()
    client = FakeClient(websocket)
    provider = TwelveDataMarketDataStreamProvider(
        lambda _: client,
        queue_capacity=10,
        heartbeat_seconds=60,
        clock=lambda: START,
    )
    await provider.subscribe_quote(EUR)

    assert client.on_event is not None
    client.on_event(
        {
            "event": "price",
            "symbol": "EUR/USD",
            "price": "1.08510",
            "timestamp": int(START.timestamp()),
        }
    )

    quote = await next_event(provider.events)
    assert isinstance(quote, StreamQuote)
    assert quote.quote.symbol == "EUR/USD"
    assert quote.quote.price == Decimal("1.08510")
    assert quote.quote.provider_time == START
    await provider.close()


@pytest.mark.parametrize("symbol", [WTI, SPY, QQQ])
async def test_provider_streams_validated_wti_and_etf_symbols(
    symbol: SupportedSymbol,
) -> None:
    websocket = FakeWebSocket()
    client = FakeClient(websocket)
    provider = TwelveDataMarketDataStreamProvider(
        lambda _: client,
        queue_capacity=10,
        heartbeat_seconds=60,
    )
    await provider.subscribe_quote(symbol)

    assert client.on_event is not None
    client.on_event(
        {
            "event": "price",
            "symbol": symbol.provider_symbol,
            "price": "100.1250",
            "timestamp": int(START.timestamp()),
        }
    )

    quote = await next_event(provider.events)
    assert isinstance(quote, StreamQuote)
    assert quote.quote.symbol == symbol.symbol
    assert quote.quote.asset_class == symbol.asset_class
    assert quote.quote.price == Decimal("100.1250")
    await provider.close()


async def test_provider_rejects_malformed_unknown_or_non_price_payloads() -> None:
    websocket = FakeWebSocket()
    client = FakeClient(websocket)
    provider = TwelveDataMarketDataStreamProvider(
        lambda _: client,
        queue_capacity=10,
        heartbeat_seconds=60,
    )
    await provider.subscribe_quote(EUR)

    assert client.on_event is not None
    client.on_event({"event": "heartbeat", "symbol": "EUR/USD", "price": "1.0"})
    client.on_event({"event": "price", "symbol": "USD/CHF", "price": "1.0"})
    client.on_event({"event": "price", "symbol": "EUR/USD", "price": "-1"})
    await asyncio.sleep(0.01)

    assert provider.events.empty()
    await provider.close()


async def test_provider_heartbeat_runs_on_configured_cadence() -> None:
    websocket = FakeWebSocket()
    client = FakeClient(websocket)
    provider = TwelveDataMarketDataStreamProvider(
        lambda _: client,
        queue_capacity=10,
        heartbeat_seconds=0.01,
    )
    await provider.subscribe_quote(EUR)
    await asyncio.sleep(0.03)

    assert websocket.heartbeats >= 1
    await provider.close()


async def test_stream_builder_selects_key_on_connect_and_reuses_live_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    used_keys: list[str] = []

    class FakeTDClient:
        def __init__(self, apikey: str) -> None:
            used_keys.append(apikey)
            self.websocket_instance = FakeWebSocket()

        def websocket(self, **defaults: object) -> FakeWebSocket:
            on_event = defaults.get("on_event")
            assert callable(on_event)
            return self.websocket_instance

    monkeypatch.setattr(stream_module, "TDClient", FakeTDClient)
    provider = build_twelvedata_market_data_stream_provider(
        ("key-a", "key-b"),
        queue_capacity=10,
        heartbeat_seconds=60,
    )

    await provider.subscribe_quote(EUR)
    await provider.subscribe_quote(WTI)
    assert used_keys == ["key-a"]

    await provider.close()
    await provider.subscribe_quote(EUR)
    assert used_keys == ["key-a", "key-b"]


async def test_provider_heartbeat_failure_emits_quote_reconnecting_signal() -> None:
    class FailingHeartbeat(FakeWebSocket):
        def heartbeat(self) -> None:
            raise RuntimeError("heartbeat failed")

    websocket = FailingHeartbeat()
    client = FakeClient(websocket)
    provider = TwelveDataMarketDataStreamProvider(
        lambda _: client,
        queue_capacity=10,
        heartbeat_seconds=0.01,
    )
    await provider.subscribe_quote(EUR)

    signal = await next_event(provider.events)
    assert isinstance(signal, ProviderSignal)
    assert signal.state == "RECONNECTING"
    assert signal.interests == (QuoteInterest("EUR/USD", "TWELVE_DATA", "EUR/USD"),)
    await provider.close()
