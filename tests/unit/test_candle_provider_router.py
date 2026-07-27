from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.candles import Candle
from app.domain.errors import ProviderUnavailableError
from app.domain.symbols import SupportedSymbol
from app.services.candle_provider_router import CandleProviderRouter

BTC = SupportedSymbol("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True, 2)
TWELVEDATA_BTC = SupportedSymbol("BTC/USD", "CRYPTO", "TWELVE_DATA", "BTC/USD", True, 2)
EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True, 5)
WTI = SupportedSymbol("WTI", "COMMODITY", "TWELVE_DATA", "WTI", True, 2)
AAPL = SupportedSymbol("AAPL", "US_STOCK", "TWELVE_DATA", "AAPL", True, 2)
SPY = SupportedSymbol("SPY", "ETF", "TWELVE_DATA", "SPY", True, 2)
SPX = SupportedSymbol("SPX", "STOCK_INDEX", "YFINANCE", "^GSPC", True, 2)
UNKNOWN = SupportedSymbol("XAU/USD", "COMMODITY", "UNKNOWN", "XAU/USD", True, 2)
YFINANCE_SILVER = SupportedSymbol("XAG/USD", "COMMODITY", "YFINANCE", "SI=F", True, 3)
START = datetime(2026, 6, 22, 0, 0, tzinfo=UTC)


def make_candle(symbol: SupportedSymbol) -> Candle:
    return Candle(
        symbol=symbol.symbol,
        asset_class=symbol.asset_class,
        provider=symbol.provider,
        provider_symbol=symbol.provider_symbol,
        timeframe="4h",
        open_time=START,
        close_time=START + timedelta(hours=4) - timedelta(milliseconds=1),
        open=Decimal("1"),
        high=Decimal("2"),
        low=Decimal("1"),
        close=Decimal("1.5"),
        volume=Decimal("0"),
        complete=True,
    )


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[SupportedSymbol, str, str, datetime, datetime, int]] = []

    async def fetch_candles(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[Candle]:
        self.calls.append((symbol, timeframe, provider_interval, start, end, limit))
        return [make_candle(symbol)]


@pytest.mark.parametrize(
    ("symbol", "provider_name"),
    [
        (BTC, "BINANCE_SPOT"),
        (TWELVEDATA_BTC, "TWELVE_DATA"),
        (EUR, "TWELVE_DATA"),
        (WTI, "TWELVE_DATA"),
        (AAPL, "TWELVE_DATA"),
        (SPY, "TWELVE_DATA"),
        (SPX, "YFINANCE"),
        (YFINANCE_SILVER, "YFINANCE"),
    ],
)
async def test_router_dispatches_by_persisted_provider(
    symbol: SupportedSymbol,
    provider_name: str,
) -> None:
    binance = FakeProvider()
    twelvedata = FakeProvider()
    yfinance = FakeProvider()
    router = CandleProviderRouter(
        {"BINANCE_SPOT": binance, "TWELVE_DATA": twelvedata, "YFINANCE": yfinance}
    )

    result = await router.fetch_candles(
        symbol,
        "4h",
        "4h",
        START,
        START + timedelta(hours=4),
        1,
    )

    providers = {
        "BINANCE_SPOT": binance,
        "TWELVE_DATA": twelvedata,
        "YFINANCE": yfinance,
    }
    selected = providers[provider_name]
    assert result == [make_candle(symbol)]
    assert selected.calls == [
        (
            symbol,
            "4h",
            "4h",
            START,
            START + timedelta(hours=4),
            1,
        )
    ]
    assert all(provider is selected or provider.calls == [] for provider in providers.values())


async def test_router_rejects_unregistered_provider_without_fallback() -> None:
    binance = FakeProvider()
    router = CandleProviderRouter({"BINANCE_SPOT": binance})

    with pytest.raises(ProviderUnavailableError):
        await router.fetch_candles(
            UNKNOWN,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )

    assert binance.calls == []


async def test_yfinance_symbols_raise_unavailable_without_fallback_when_unwired() -> None:
    binance = FakeProvider()
    router = CandleProviderRouter({"BINANCE_SPOT": binance})

    with pytest.raises(ProviderUnavailableError):
        await router.fetch_candles(
            YFINANCE_SILVER,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )

    assert binance.calls == []
