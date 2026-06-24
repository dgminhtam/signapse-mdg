import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.streams import CandleInterest, StreamCandle, StreamQuote
from app.domain.symbols import SupportedSymbol
from app.providers.price_tick_stream import PriceTick, PriceTickCandleBuilder
from app.providers.twelvedata_market_data_stream import TwelveDataMarketDataStreamProvider

EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True)
WTI = SupportedSymbol("WTI", "COMMODITY", "TWELVE_DATA", "WTI", True)
SPY = SupportedSymbol("SPY", "ETF", "TWELVE_DATA", "SPY", True)
QQQ = SupportedSymbol("QQQ", "ETF", "TWELVE_DATA", "QQQ", True)
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
    await provider.subscribe_candle(EUR, "1m", "1m")

    assert websocket.connected is True
    assert client.websocket_calls == 1
    assert websocket.subscribed == ["EUR/USD"]

    await provider.unsubscribe(CandleInterest("EUR/USD", "1m"))
    assert websocket.unsubscribed == []
    await provider.close()
    assert websocket.disconnected is True


async def test_provider_reuses_connection_across_forex_wti_and_etfs() -> None:
    websocket = FakeWebSocket()
    client = FakeClient(websocket)
    provider = TwelveDataMarketDataStreamProvider(
        lambda _: client,
        queue_capacity=10,
        heartbeat_seconds=60,
    )

    for symbol in (EUR, WTI, SPY, QQQ):
        await provider.subscribe_quote(symbol)

    assert client.websocket_calls == 1
    assert websocket.subscribed == ["EUR/USD", "WTI", "SPY", "QQQ"]
    await provider.close()


async def test_provider_bridges_valid_price_payload_to_quote_and_candle_events() -> None:
    websocket = FakeWebSocket()
    client = FakeClient(websocket)
    provider = TwelveDataMarketDataStreamProvider(
        lambda _: client,
        queue_capacity=10,
        heartbeat_seconds=60,
    )
    await provider.subscribe_quote(EUR)
    await provider.subscribe_candle(EUR, "1m", "1m")

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
    candle = await next_event(provider.events)

    assert isinstance(quote, StreamQuote)
    assert quote.quote.symbol == "EUR/USD"
    assert quote.quote.price == Decimal("1.08510")
    assert isinstance(candle, StreamCandle)
    assert candle.candle.open_time == datetime(2026, 6, 22, 0, 0, tzinfo=UTC)
    assert candle.candle.volume == Decimal("0")
    assert candle.candle.complete is False
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


def test_twelvedata_candle_builder_bucket_boundaries_and_no_synthetic_gaps() -> None:
    builder = PriceTickCandleBuilder()
    first = PriceTick(EUR, Decimal("1.00"), datetime(2026, 6, 22, 0, 0, 10, tzinfo=UTC), START)
    second = PriceTick(EUR, Decimal("1.20"), datetime(2026, 6, 22, 0, 0, 50, tzinfo=UTC), START)
    later = PriceTick(EUR, Decimal("1.10"), datetime(2026, 6, 22, 0, 5, 1, tzinfo=UTC), START)

    first_events = builder.apply_tick(first, "1m")
    second_events = builder.apply_tick(second, "1m")
    later_events = builder.apply_tick(later, "1m")

    assert len(first_events) == 1
    assert first_events[0].candle.open == Decimal("1.00")
    assert first_events[0].candle.volume == Decimal("0")
    assert second_events[0].candle.high == Decimal("1.20")
    assert len(later_events) == 2
    assert later_events[0].candle.complete is True
    assert later_events[1].candle.open_time == datetime(2026, 6, 22, 0, 5, tzinfo=UTC)


@pytest.mark.parametrize(
    ("timeframe", "tick_time", "expected_open"),
    [
        (
            "1m",
            datetime(2026, 6, 22, 0, 0, 59, tzinfo=UTC),
            datetime(2026, 6, 22, 0, 0, tzinfo=UTC),
        ),
        ("5m", datetime(2026, 6, 22, 0, 7, tzinfo=UTC), datetime(2026, 6, 22, 0, 5, tzinfo=UTC)),
        ("15m", datetime(2026, 6, 22, 0, 29, tzinfo=UTC), datetime(2026, 6, 22, 0, 15, tzinfo=UTC)),
        ("1h", datetime(2026, 6, 22, 1, 59, tzinfo=UTC), datetime(2026, 6, 22, 1, 0, tzinfo=UTC)),
        ("1d", datetime(2026, 6, 22, 23, 59, tzinfo=UTC), datetime(2026, 6, 22, 0, 0, tzinfo=UTC)),
    ],
)
def test_forex_candle_builder_supports_public_timeframe_boundaries(
    timeframe: str,
    tick_time: datetime,
    expected_open: datetime,
) -> None:
    builder = PriceTickCandleBuilder()
    events = builder.apply_tick(PriceTick(EUR, Decimal("1.00"), tick_time, START), timeframe)

    assert events[0].candle.open_time == expected_open


def test_forex_candle_builder_filters_closed_weekend_bucket() -> None:
    builder = PriceTickCandleBuilder()
    events = builder.apply_tick(
        PriceTick(
            EUR,
            Decimal("1.00"),
            datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
            START,
        ),
        "1h",
    )

    assert events == []


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
def test_candle_builder_applies_wti_and_etf_sessions(
    symbol: SupportedSymbol,
    closed_time: datetime,
    open_time: datetime,
) -> None:
    builder = PriceTickCandleBuilder()

    assert (
        builder.apply_tick(
            PriceTick(symbol, Decimal("100"), closed_time, closed_time),
            "1h",
        )
        == []
    )
    events = builder.apply_tick(
        PriceTick(symbol, Decimal("101"), open_time, open_time),
        "1h",
    )

    assert len(events) == 1
    assert events[0].candle.symbol == symbol.symbol
    assert events[0].candle.open_time == open_time
