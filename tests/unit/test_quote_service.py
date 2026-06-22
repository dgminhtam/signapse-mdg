import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.cache.quote_cache import QuoteCache
from app.domain.errors import ProviderUnavailableError, QuoteRequestError
from app.domain.quotes import ProviderQuoteBatch, Quote
from app.domain.symbols import SupportedSymbol
from app.services.quote_provider_router import QuoteProviderRouter
from app.services.quotes import QuoteService, parse_symbols


class FakeSymbolRepository:
    def __init__(self, symbols: list[SupportedSymbol]) -> None:
        self.symbols = symbols

    async def list_enabled(self) -> list[SupportedSymbol]:
        return self.symbols


class FakeProvider:
    def __init__(
        self,
        prices: dict[str, Decimal] | None = None,
        unavailable: set[str] | None = None,
        error: bool = False,
        gate: asyncio.Event | None = None,
    ) -> None:
        self.prices = prices or {}
        self.unavailable = unavailable or set()
        self.error = error
        self.gate = gate
        self.calls: list[list[str]] = []

    async def fetch_latest_prices(self, symbols: list[SupportedSymbol]) -> ProviderQuoteBatch:
        provider_symbols = [symbol.provider_symbol for symbol in symbols]
        self.calls.append(provider_symbols)
        if self.gate is not None:
            await self.gate.wait()
        if self.error:
            raise ProviderUnavailableError
        return ProviderQuoteBatch(
            prices=self.prices,
            unavailable_symbols=frozenset(self.unavailable),
        )


class FakeProviderSymbolProvider:
    def __init__(
        self,
        prices: dict[str, Decimal] | None = None,
        error: bool = False,
    ) -> None:
        self.prices = prices or {}
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
            unavailable_symbols=frozenset(),
        )


BTC = SupportedSymbol("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True)
ETH = SupportedSymbol("ETH/USD", "CRYPTO", "BINANCE_SPOT", "ETHUSD", True)
EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True)
GBP = SupportedSymbol("GBP/USD", "FOREX", "TWELVE_DATA", "GBP/USD", True)
NOW = datetime(2026, 6, 19, 10, 30, tzinfo=UTC)


def build_service(
    provider: FakeProvider,
    cache: QuoteCache | None = None,
    now: datetime = NOW,
) -> QuoteService:
    return QuoteService(
        repository=FakeSymbolRepository([BTC, ETH]),
        provider=provider,
        cache=cache or QuoteCache(),
        cache_ttl_seconds=10,
        stale_after_seconds=30,
        clock=lambda: now,
    )


def build_mixed_service(
    provider: QuoteProviderRouter,
    cache: QuoteCache | None = None,
    now: datetime = NOW,
) -> QuoteService:
    return QuoteService(
        repository=FakeSymbolRepository([BTC, ETH, EUR, GBP]),
        provider=provider,
        cache=cache or QuoteCache(),
        cache_ttl_seconds=10,
        stale_after_seconds=30,
        clock=lambda: now,
    )


def test_parse_symbols_deduplicates_in_first_occurrence_order() -> None:
    assert parse_symbols(" ETH/USD, BTC/USD,ETH/USD ", 10) == ["ETH/USD", "BTC/USD"]


@pytest.mark.parametrize("raw", [None, "", " , , "])
def test_parse_symbols_rejects_missing_or_empty_input(raw: str | None) -> None:
    with pytest.raises(QuoteRequestError) as exc_info:
        parse_symbols(raw, 10)
    assert exc_info.value.code == "INVALID_SYMBOLS"


def test_parse_symbols_rejects_too_many_distinct_symbols() -> None:
    with pytest.raises(QuoteRequestError) as exc_info:
        parse_symbols("BTC/USD,ETH/USD", 1)
    assert exc_info.value.code == "TOO_MANY_SYMBOLS"


async def test_service_batches_supported_symbols_and_preserves_request_order() -> None:
    provider = FakeProvider(prices={"BTCUSD": Decimal("10.10"), "ETHUSD": Decimal("20.20")})

    result = await build_service(provider).get_latest_quotes(["ETH/USD", "SOL/USD", "BTC/USD"])

    assert [quote.symbol for quote in result.quotes] == ["ETH/USD", "BTC/USD"]
    assert [error.symbol for error in result.errors] == ["SOL/USD"]
    assert result.errors[0].code == "UNSUPPORTED_SYMBOL"
    assert provider.calls == [["ETHUSD", "BTCUSD"]]


async def test_service_uses_cache_within_ttl() -> None:
    cache = QuoteCache()
    cached = Quote(
        symbol="BTC/USD",
        asset_class="CRYPTO",
        provider="BINANCE_SPOT",
        provider_symbol="BTCUSD",
        price=Decimal("9.99"),
        volume=None,
        provider_time=None,
        received_at=NOW - timedelta(seconds=5),
    )
    await cache.put_many([cached])
    provider = FakeProvider()

    result = await build_service(provider, cache).get_latest_quotes(["BTC/USD"])

    assert result.quotes == [cached]
    assert provider.calls == []


async def test_service_returns_fresh_cache_when_refresh_fails() -> None:
    cache = QuoteCache()
    cached = Quote(
        "BTC/USD",
        "CRYPTO",
        "BINANCE_SPOT",
        "BTCUSD",
        Decimal("9.99"),
        None,
        None,
        NOW - timedelta(seconds=20),
    )
    await cache.put_many([cached])

    result = await build_service(FakeProvider(error=True), cache).get_latest_quotes(["BTC/USD"])

    assert result.quotes == [cached]
    assert result.errors == []


async def test_service_rejects_stale_cache_when_refresh_fails() -> None:
    cache = QuoteCache()
    await cache.put_many(
        [
            Quote(
                "BTC/USD",
                "CRYPTO",
                "BINANCE_SPOT",
                "BTCUSD",
                Decimal("9.99"),
                None,
                None,
                NOW - timedelta(seconds=31),
            )
        ]
    )

    result = await build_service(FakeProvider(error=True), cache).get_latest_quotes(["BTC/USD"])

    assert result.quotes == []
    assert result.errors[0].code == "DATA_STALE"


async def test_service_isolates_partial_provider_payload_failure() -> None:
    provider = FakeProvider(
        prices={"BTCUSD": Decimal("10")},
        unavailable={"ETHUSD"},
    )

    result = await build_service(provider).get_latest_quotes(["BTC/USD", "ETH/USD"])

    assert [quote.symbol for quote in result.quotes] == ["BTC/USD"]
    assert [(error.symbol, error.code) for error in result.errors] == [
        ("ETH/USD", "PROVIDER_UNAVAILABLE")
    ]


async def test_service_coalesces_concurrent_refreshes() -> None:
    gate = asyncio.Event()
    provider = FakeProvider(prices={"BTCUSD": Decimal("10")}, gate=gate)
    service = build_service(provider)

    first = asyncio.create_task(service.get_latest_quotes(["BTC/USD"]))
    second = asyncio.create_task(service.get_latest_quotes(["BTC/USD"]))
    await asyncio.sleep(0)
    gate.set()
    first_result, second_result = await asyncio.gather(first, second)

    assert provider.calls == [["BTCUSD"]]
    assert first_result.quotes[0].price == Decimal("10")
    assert second_result.quotes[0].price == Decimal("10")


async def test_service_preserves_request_order_for_mixed_provider_quotes() -> None:
    binance = FakeProviderSymbolProvider({"BTCUSD": Decimal("10")})
    twelvedata = FakeProviderSymbolProvider({"EUR/USD": Decimal("1.10")})
    service = build_mixed_service(
        QuoteProviderRouter({"BINANCE_SPOT": binance, "TWELVE_DATA": twelvedata})
    )

    result = await service.get_latest_quotes(["EUR/USD", "BTC/USD"])

    assert [quote.symbol for quote in result.quotes] == ["EUR/USD", "BTC/USD"]
    assert [quote.price for quote in result.quotes] == [Decimal("1.10"), Decimal("10")]
    assert result.errors == []
    assert binance.calls == [["BTCUSD"]]
    assert twelvedata.calls == [["EUR/USD"]]


async def test_service_returns_crypto_when_twelvedata_provider_is_missing() -> None:
    binance = FakeProviderSymbolProvider({"BTCUSD": Decimal("10")})
    service = build_mixed_service(QuoteProviderRouter({"BINANCE_SPOT": binance}))

    result = await service.get_latest_quotes(["BTC/USD", "EUR/USD"])

    assert [quote.symbol for quote in result.quotes] == ["BTC/USD"]
    assert result.quotes[0].price == Decimal("10")
    assert [(error.symbol, error.code) for error in result.errors] == [
        ("EUR/USD", "PROVIDER_UNAVAILABLE")
    ]


async def test_service_isolates_twelvedata_failure_from_binance_success() -> None:
    binance = FakeProviderSymbolProvider({"BTCUSD": Decimal("10")})
    twelvedata = FakeProviderSymbolProvider(error=True)
    service = build_mixed_service(
        QuoteProviderRouter({"BINANCE_SPOT": binance, "TWELVE_DATA": twelvedata})
    )

    result = await service.get_latest_quotes(["BTC/USD", "GBP/USD"])

    assert [quote.symbol for quote in result.quotes] == ["BTC/USD"]
    assert result.quotes[0].price == Decimal("10")
    assert [(error.symbol, error.code) for error in result.errors] == [
        ("GBP/USD", "PROVIDER_UNAVAILABLE")
    ]
