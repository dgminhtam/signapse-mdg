import asyncio
from datetime import UTC, datetime

import pytest

from app.domain.errors import ProviderUnavailableError
from app.domain.streams import (
    ProviderSignal,
    ProviderStreamEvent,
    QuoteInterest,
    StreamInterest,
)
from app.domain.symbols import SupportedSymbol
from app.services.stream_provider_router import MultiProviderStreamProvider

BTC = SupportedSymbol("BTC/USD", "CRYPTO", "TWELVE_DATA", "BTC/USD", True, 2)
BINANCE_BTC = SupportedSymbol("BTC/BINANCE", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True, 2)
EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True, 5)
UNKNOWN = SupportedSymbol("X/USD", "FOREX", "MISSING", "X/USD", True, 5)
YFINANCE_SILVER = SupportedSymbol("XAG/USD", "COMMODITY", "YFINANCE", "SI=F", True, 3)


class FakeProvider:
    def __init__(self) -> None:
        self.events: asyncio.Queue[ProviderStreamEvent] = asyncio.Queue()
        self.quote_subscriptions: list[str] = []
        self.unsubscribed: list[StreamInterest] = []
        self.closed = False

    async def subscribe_quote(self, symbol: SupportedSymbol) -> None:
        self.quote_subscriptions.append(symbol.symbol)

    async def unsubscribe(self, interest: StreamInterest) -> None:
        self.unsubscribed.append(interest)

    async def close(self) -> None:
        self.closed = True


async def test_router_routes_mixed_symbols_by_provider_and_forwards_events() -> None:
    binance = FakeProvider()
    twelvedata = FakeProvider()
    yfinance = FakeProvider()
    router = MultiProviderStreamProvider(
        {
            "BINANCE_SPOT": binance,
            "TWELVE_DATA": twelvedata,
            "YFINANCE": yfinance,
        },
        queue_capacity=10,
    )
    try:
        await router.subscribe_quote(BTC)
        await router.subscribe_quote(BINANCE_BTC)
        await router.subscribe_quote(EUR)
        await router.subscribe_quote(YFINANCE_SILVER)

        assert binance.quote_subscriptions == ["BTC/BINANCE"]
        assert twelvedata.quote_subscriptions == ["BTC/USD", "EUR/USD"]
        assert yfinance.quote_subscriptions == ["XAG/USD"]

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

    await router.subscribe_quote(BINANCE_BTC)
    await router.subscribe_quote(EUR)
    await router.unsubscribe(QuoteInterest("BTC/BINANCE"))
    await router.unsubscribe(QuoteInterest("BTC/BINANCE"))
    await router.unsubscribe(QuoteInterest("EUR/USD"))
    await router.close()

    assert binance.unsubscribed == [QuoteInterest("BTC/BINANCE")]
    assert twelvedata.unsubscribed == [QuoteInterest("EUR/USD")]
    assert binance.closed is True
    assert twelvedata.closed is True


async def test_router_rejects_unsupported_provider_mapping() -> None:
    router = MultiProviderStreamProvider({"BINANCE_SPOT": FakeProvider()}, queue_capacity=10)

    with pytest.raises(ProviderUnavailableError):
        await router.subscribe_quote(UNKNOWN)

    await router.close()


async def test_yfinance_symbols_raise_unavailable_until_provider_is_wired() -> None:
    binance = FakeProvider()
    router = MultiProviderStreamProvider({"BINANCE_SPOT": binance}, queue_capacity=10)

    with pytest.raises(ProviderUnavailableError):
        await router.subscribe_quote(YFINANCE_SILVER)

    assert binance.quote_subscriptions == []
    await router.close()


async def test_yfinance_symbols_route_only_to_yfinance_provider() -> None:
    binance = FakeProvider()
    yfinance = FakeProvider()
    router = MultiProviderStreamProvider(
        {"BINANCE_SPOT": binance, "YFINANCE": yfinance},
        queue_capacity=10,
    )

    await router.subscribe_quote(YFINANCE_SILVER)

    assert yfinance.quote_subscriptions == ["XAG/USD"]
    assert binance.quote_subscriptions == []
    await router.close()
