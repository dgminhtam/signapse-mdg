from decimal import Decimal

from app.domain.errors import ProviderUnavailableError
from app.domain.quotes import ProviderQuoteBatch
from app.domain.symbols import SupportedSymbol
from app.services.quote_provider_router import QuoteProviderRouter

BTC = SupportedSymbol("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True)
ETH = SupportedSymbol("ETH/USD", "CRYPTO", "BINANCE_SPOT", "ETHUSD", True)
EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True)
GBP = SupportedSymbol("GBP/USD", "FOREX", "TWELVE_DATA", "GBP/USD", True)
UNKNOWN = SupportedSymbol("XAU/USD", "COMMODITY", "UNKNOWN", "XAU/USD", True)


class FakeProvider:
    def __init__(
        self,
        prices: dict[str, Decimal] | None = None,
        unavailable: set[str] | None = None,
        error: bool = False,
    ) -> None:
        self.prices = prices or {}
        self.unavailable = unavailable or set()
        self.error = error
        self.calls: list[list[str]] = []

    async def fetch_latest_prices(self, provider_symbols: list[str]) -> ProviderQuoteBatch:
        self.calls.append(provider_symbols)
        if self.error:
            raise ProviderUnavailableError
        return ProviderQuoteBatch(
            prices={
                symbol: self.prices[symbol] for symbol in provider_symbols if symbol in self.prices
            },
            unavailable_symbols=frozenset(
                symbol for symbol in provider_symbols if symbol in self.unavailable
            ),
        )


async def test_router_dispatches_mixed_symbols_by_provider() -> None:
    binance = FakeProvider({"BTCUSD": Decimal("10"), "ETHUSD": Decimal("20")})
    twelvedata = FakeProvider({"EUR/USD": Decimal("1.10"), "GBP/USD": Decimal("1.25")})
    router = QuoteProviderRouter({"BINANCE_SPOT": binance, "TWELVE_DATA": twelvedata})

    result = await router.fetch_latest_prices([BTC, EUR, ETH, GBP])

    assert binance.calls == [["BTCUSD", "ETHUSD"]]
    assert twelvedata.calls == [["EUR/USD", "GBP/USD"]]
    assert result.prices == {
        "BTCUSD": Decimal("10"),
        "ETHUSD": Decimal("20"),
        "EUR/USD": Decimal("1.10"),
        "GBP/USD": Decimal("1.25"),
    }
    assert result.unavailable_symbols == frozenset()


async def test_router_isolates_provider_group_failure() -> None:
    binance = FakeProvider({"BTCUSD": Decimal("10")})
    twelvedata = FakeProvider(error=True)
    router = QuoteProviderRouter({"BINANCE_SPOT": binance, "TWELVE_DATA": twelvedata})

    result = await router.fetch_latest_prices([BTC, EUR, GBP])

    assert binance.calls == [["BTCUSD"]]
    assert twelvedata.calls == [["EUR/USD", "GBP/USD"]]
    assert result.prices == {"BTCUSD": Decimal("10")}
    assert result.unavailable_symbols == frozenset({"EUR/USD", "GBP/USD"})


async def test_router_marks_missing_provider_configuration_unavailable() -> None:
    binance = FakeProvider({"BTCUSD": Decimal("10")})
    router = QuoteProviderRouter({"BINANCE_SPOT": binance})

    result = await router.fetch_latest_prices([BTC, EUR, UNKNOWN])

    assert binance.calls == [["BTCUSD"]]
    assert result.prices == {"BTCUSD": Decimal("10")}
    assert result.unavailable_symbols == frozenset({"EUR/USD", "XAU/USD"})


async def test_router_preserves_provider_unavailable_symbols() -> None:
    twelvedata = FakeProvider({"EUR/USD": Decimal("1.10")}, unavailable={"GBP/USD"})
    router = QuoteProviderRouter({"TWELVE_DATA": twelvedata})

    result = await router.fetch_latest_prices([EUR, GBP])

    assert result.prices == {"EUR/USD": Decimal("1.10")}
    assert result.unavailable_symbols == frozenset({"GBP/USD"})
