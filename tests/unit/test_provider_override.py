from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routes_candles import get_candle_service
from app.api.routes_historical_price import get_historical_price_service
from app.api.routes_quotes import get_quote_service
from app.cache.candle_cache import CandleCache
from app.cache.quote_cache import QuoteCache
from app.domain.candles import Candle, CandleRequest, CandleResult
from app.domain.errors import ProviderSelectionError
from app.domain.quotes import ProviderQuoteBatch, QuoteResult
from app.domain.streams import CandleInterest, QuoteInterest
from app.domain.symbols import ProviderMapping, ProviderSelection, SupportedSymbol
from app.main import app
from app.services.historical_prices import HistoricalPriceRequest, HistoricalPriceService
from app.services.provider_selection import parse_provider_values, resolve_provider_selection
from app.services.quotes import QuoteService

NOW = datetime(2026, 6, 19, 10, 30, 12, tzinfo=UTC)


def mapped_stock() -> SupportedSymbol:
    return SupportedSymbol(
        "AAPL",
        "US_STOCK",
        "TWELVE_DATA",
        "AAPL",
        True,
        2,
        provider_mappings=(
            ProviderMapping("TWELVE_DATA", "AAPL", True),
            ProviderMapping("YFINANCE", "AAPL", False),
        ),
    )


def test_provider_selection_is_case_sensitive_and_request_scoped() -> None:
    selected, selection = resolve_provider_selection(mapped_stock(), "YFINANCE")

    assert selected.provider == "YFINANCE"
    assert selected.provider_symbol == "AAPL"
    assert selection == ProviderSelection("AAPL", "YFINANCE", "AAPL", "OVERRIDE")
    assert mapped_stock().provider == "TWELVE_DATA"

    with pytest.raises(Exception) as exc_info:
        resolve_provider_selection(mapped_stock(), "yfinance")
    assert exc_info.value.code == "UNSUPPORTED_PROVIDER"


def test_provider_query_parser_rejects_empty_and_duplicate_values() -> None:
    assert parse_provider_values([]) is None
    assert parse_provider_values(["YFINANCE"]) == "YFINANCE"
    with pytest.raises(Exception) as empty:
        parse_provider_values([" "])
    assert empty.value.code == "INVALID_PROVIDER"
    with pytest.raises(Exception) as duplicate:
        parse_provider_values(["YFINANCE", "YFINANCE"])
    assert duplicate.value.code == "INVALID_PROVIDER"


def test_provider_selection_fails_closed_for_multiple_defaults() -> None:
    symbol = SupportedSymbol(
        "AAPL",
        "US_STOCK",
        "TWELVE_DATA",
        "AAPL",
        True,
        2,
        provider_mappings=(
            ProviderMapping("TWELVE_DATA", "AAPL", True),
            ProviderMapping("YFINANCE", "AAPL", True),
        ),
    )

    with pytest.raises(ProviderSelectionError) as exc_info:
        resolve_provider_selection(symbol, "YFINANCE")

    assert exc_info.value.code == "DATABASE_UNAVAILABLE"


class FakeSymbolRepository:
    async def list_enabled(self) -> list[SupportedSymbol]:
        return [mapped_stock()]


class RecordingQuoteProvider:
    def __init__(self) -> None:
        self.calls: list[list[SupportedSymbol]] = []

    async def fetch_latest_prices(
        self,
        symbols: list[SupportedSymbol],
    ) -> ProviderQuoteBatch:
        self.calls.append(symbols)
        return ProviderQuoteBatch(
            prices={symbol.provider_symbol: Decimal("123.45") for symbol in symbols},
            unavailable_symbols=frozenset(),
        )


async def test_quote_cache_isolated_between_default_and_override() -> None:
    provider = RecordingQuoteProvider()
    service = QuoteService(
        FakeSymbolRepository(),
        provider,
        QuoteCache(),
        cache_ttl_seconds=60,
        stale_after_seconds=120,
        clock=lambda: NOW,
    )

    override = await service.get_latest_quotes(["AAPL"], "YFINANCE")
    await service.get_latest_quotes(["AAPL"])

    assert isinstance(override, QuoteResult)
    assert len(provider.calls) == 2
    assert provider.calls[0][0].provider == "YFINANCE"
    assert provider.calls[1][0].provider == "TWELVE_DATA"


def make_candle(
    timeframe: str,
    open_time: datetime,
    close_time: datetime,
    *,
    complete: bool,
) -> Candle:
    return Candle(
        "AAPL",
        "US_STOCK",
        "YFINANCE",
        "AAPL",
        timeframe,
        open_time,
        close_time,
        Decimal("100"),
        Decimal("101"),
        Decimal("99"),
        Decimal("100.5"),
        Decimal("0"),
        complete,
    )


class StubHistoricalCandleService:
    def __init__(self) -> None:
        self.requests: list[CandleRequest] = []
        self.symbol = mapped_stock().with_mapping(ProviderMapping("YFINANCE", "AAPL", False))

    async def resolve_symbol(self, symbol: str, provider: str | None = None) -> SupportedSymbol:
        assert symbol == "AAPL"
        assert provider == "YFINANCE"
        return self.symbol

    async def get_candles(
        self,
        request: CandleRequest,
        *,
        resolved_symbol: SupportedSymbol,
    ) -> CandleResult:
        self.requests.append(request)
        if request.timeframe == "1m":
            candles = [
                make_candle(
                    "1m",
                    NOW.replace(second=0),
                    NOW.replace(second=59, microsecond=999000),
                    complete=True,
                )
            ]
        else:
            open_time = NOW - timedelta(minutes=5)
            candles = [
                make_candle(
                    "5m",
                    open_time,
                    NOW.replace(second=0, microsecond=0) - timedelta(milliseconds=1),
                    complete=True,
                )
            ]
        return CandleResult("AAPL", request.timeframe, request.start, request.end, candles, 2)


async def test_history_policy_keeps_provider_and_rejects_lookahead() -> None:
    service = StubHistoricalCandleService()
    history = HistoricalPriceService(service, clock=lambda: NOW)  # type: ignore[arg-type]

    result = await history.get_historical_price(HistoricalPriceRequest("AAPL", NOW, "YFINANCE"))

    assert result.priced_at == NOW - timedelta(minutes=5)
    assert [request.timeframe for request in service.requests] == ["1m", "5m"]
    assert all(request.provider == "YFINANCE" for request in service.requests)


async def test_candle_cache_and_stream_interests_include_provider_identity() -> None:
    cache = CandleCache()
    first = make_candle(
        "1m",
        NOW.replace(second=0),
        NOW.replace(second=59, microsecond=999000),
        complete=False,
    )
    second = first.__class__(
        first.symbol,
        first.asset_class,
        "TWELVE_DATA",
        "AAPL",
        first.timeframe,
        first.open_time,
        first.close_time,
        first.open,
        first.high,
        first.low,
        Decimal("200"),
        first.volume,
        first.complete,
    )
    await cache.put(first)
    await cache.put(second)

    assert await cache.get("AAPL", "1m", "YFINANCE", "AAPL") == first
    assert await cache.get("AAPL", "1m", "TWELVE_DATA", "AAPL") == second
    assert QuoteInterest("AAPL", "YFINANCE", "AAPL") != QuoteInterest("AAPL", "TWELVE_DATA", "AAPL")
    assert CandleInterest("AAPL", "1m", "YFINANCE", "AAPL") != CandleInterest(
        "AAPL", "1m", "TWELVE_DATA", "AAPL"
    )


class StubQuoteService:
    def __init__(self) -> None:
        self.provider: str | None = None

    async def get_latest_quotes(
        self,
        symbols: list[str],
        provider: str | None = None,
    ) -> QuoteResult:
        self.provider = provider
        return QuoteResult([], [], {symbol: 2 for symbol in symbols})


class StubCandleService:
    def __init__(self) -> None:
        self.request: CandleRequest | None = None

    async def get_candles(self, request: CandleRequest) -> CandleResult:
        self.request = request
        return CandleResult("AAPL", request.timeframe, request.start, request.end, [], 2)


class StubHistoryService:
    def __init__(self) -> None:
        self.request: HistoricalPriceRequest | None = None

    async def get_historical_price(self, request: HistoricalPriceRequest):
        self.request = request
        from app.services.historical_prices import HistoricalPriceResult

        return HistoricalPriceResult("AAPL", Decimal("1"), NOW, 2, "1m")


async def _client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_http_routes_forward_exact_provider_and_reject_duplicate_provider() -> None:
    client_iterator = _client()
    client = await client_iterator.__anext__()
    quote_service = StubQuoteService()
    candle_service = StubCandleService()
    history_service = StubHistoryService()
    app.dependency_overrides[get_quote_service] = lambda: quote_service
    app.dependency_overrides[get_candle_service] = lambda: candle_service
    app.dependency_overrides[get_historical_price_service] = lambda: history_service
    try:
        quote_response = await client.get(
            "/v1/quotes",
            params=[("symbols", "AAPL"), ("provider", "YFINANCE")],
        )
        assert quote_response.status_code == 200
        assert quote_service.provider == "YFINANCE"

        duplicate = await client.get(
            "/v1/quotes",
            params=[("symbols", "AAPL"), ("provider", "YFINANCE"), ("provider", "YFINANCE")],
        )
        assert duplicate.status_code == 400
        assert duplicate.json()["error"]["code"] == "INVALID_PROVIDER"

        candle_response = await client.get(
            "/v1/candles",
            params={
                "symbol": "AAPL",
                "timeframe": "1m",
                "from": "2026-06-19T10:00:00Z",
                "to": "2026-06-19T10:01:00Z",
                "provider": "YFINANCE",
            },
        )
        assert candle_response.status_code == 200
        assert candle_service.request is not None
        assert candle_service.request.provider == "YFINANCE"

        history_response = await client.get(
            "/v1/historical-price",
            params={"symbol": "AAPL", "at": "2026-06-19T10:30:12Z", "provider": "YFINANCE"},
        )
        assert history_response.status_code == 200
        assert history_service.request is not None
        assert history_service.request.provider == "YFINANCE"
    finally:
        app.dependency_overrides.clear()
        await client.aclose()
