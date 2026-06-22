from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.candles import Candle
from app.domain.errors import ProviderUnavailableError
from app.domain.symbols import SupportedSymbol
from app.services.candle_provider_router import CandleProviderRouter

BTC = SupportedSymbol("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True)
EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True)
UNKNOWN = SupportedSymbol("XAU/USD", "COMMODITY", "UNKNOWN", "XAU/USD", True)
START = datetime(2026, 6, 22, 0, 0, tzinfo=UTC)


def make_candle(symbol: SupportedSymbol) -> Candle:
    return Candle(
        symbol=symbol.symbol,
        asset_class=symbol.asset_class,
        provider=symbol.provider,
        provider_symbol=symbol.provider_symbol,
        timeframe="1m",
        open_time=START,
        close_time=START + timedelta(minutes=1) - timedelta(milliseconds=1),
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
    [(BTC, "BINANCE_SPOT"), (EUR, "TWELVE_DATA")],
)
async def test_router_dispatches_by_persisted_provider(
    symbol: SupportedSymbol,
    provider_name: str,
) -> None:
    binance = FakeProvider()
    twelvedata = FakeProvider()
    router = CandleProviderRouter({"BINANCE_SPOT": binance, "TWELVE_DATA": twelvedata})

    result = await router.fetch_candles(
        symbol,
        "1m",
        "1m",
        START,
        START + timedelta(minutes=1),
        1,
    )

    selected = binance if provider_name == "BINANCE_SPOT" else twelvedata
    other = twelvedata if provider_name == "BINANCE_SPOT" else binance
    assert result == [make_candle(symbol)]
    assert selected.calls == [
        (
            symbol,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )
    ]
    assert other.calls == []


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
