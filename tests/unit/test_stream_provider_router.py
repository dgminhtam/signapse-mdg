import asyncio
from datetime import UTC, datetime

import pytest

from app.domain.errors import ProviderUnavailableError
from app.domain.streams import (
    CandleInterest,
    ProviderSignal,
    ProviderStreamEvent,
    QuoteInterest,
    StreamInterest,
)
from app.domain.symbols import SupportedSymbol
from app.services.stream_provider_router import MultiProviderStreamProvider

BTC = SupportedSymbol("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True)
EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True)
UNKNOWN = SupportedSymbol("X/USD", "FOREX", "MISSING", "X/USD", True)


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


async def test_router_routes_mixed_interests_by_provider_and_forwards_events() -> None:
    binance = FakeProvider()
    twelvedata = FakeProvider()
    router = MultiProviderStreamProvider(
        {"BINANCE_SPOT": binance, "TWELVE_DATA": twelvedata},
        queue_capacity=10,
    )
    try:
        await router.subscribe_quote(BTC)
        await router.subscribe_candle(BTC, "1m", "1m")
        await router.subscribe_quote(EUR)
        await router.subscribe_candle(EUR, "1m", "1m")

        assert binance.quote_subscriptions == ["BTC/USD"]
        assert binance.candle_subscriptions == [("BTC/USD", "1m", "1m")]
        assert twelvedata.quote_subscriptions == ["EUR/USD"]
        assert twelvedata.candle_subscriptions == [("EUR/USD", "1m", "1m")]

        signal = ProviderSignal(
            "RECONNECTING",
            (QuoteInterest("EUR/USD"),),
            datetime(2026, 6, 19, tzinfo=UTC),
        )
        await twelvedata.events.put(signal)

        assert await asyncio.wait_for(router.events.get(), timeout=1) == signal
    finally:
        await router.close()


async def test_router_unsubscribes_idempotently_and_closes_children() -> None:
    binance = FakeProvider()
    twelvedata = FakeProvider()
    router = MultiProviderStreamProvider(
        {"BINANCE_SPOT": binance, "TWELVE_DATA": twelvedata},
        queue_capacity=10,
    )

    await router.subscribe_quote(BTC)
    await router.subscribe_candle(EUR, "1m", "1m")
    await router.unsubscribe(QuoteInterest("BTC/USD"))
    await router.unsubscribe(QuoteInterest("BTC/USD"))
    await router.unsubscribe(CandleInterest("EUR/USD", "1m"))
    await router.close()

    assert binance.unsubscribed == [QuoteInterest("BTC/USD")]
    assert twelvedata.unsubscribed == [CandleInterest("EUR/USD", "1m")]
    assert binance.closed is True
    assert twelvedata.closed is True


async def test_router_rejects_unsupported_provider_mapping() -> None:
    router = MultiProviderStreamProvider({"BINANCE_SPOT": FakeProvider()}, queue_capacity=10)

    with pytest.raises(ProviderUnavailableError):
        await router.subscribe_quote(UNKNOWN)

    await router.close()
