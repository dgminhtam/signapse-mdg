from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routes_quotes import (
    get_quote_cache,
    get_quote_provider,
    get_quote_repository,
    get_quote_service,
)
from app.cache.quote_cache import QuoteCache
from app.core.config import Settings, get_settings
from app.domain.errors import DatabaseUnavailableError
from app.domain.quotes import ProviderQuoteBatch, Quote, QuoteError, QuoteResult
from app.domain.symbols import SupportedSymbol
from app.main import app
from app.services.quote_provider_router import QuoteProviderRouter


class StubQuoteService:
    def __init__(
        self,
        result: QuoteResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or QuoteResult(quotes=[], errors=[])
        self.error = error
        self.requested: list[str] = []

    async def get_latest_quotes(self, requested_symbols: list[str]) -> QuoteResult:
        self.requested = requested_symbols
        if self.error is not None:
            raise self.error
        return self.result


class FakeSymbolRepository:
    async def list_enabled(self) -> list[SupportedSymbol]:
        return [
            SupportedSymbol("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True),
            SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True),
        ]


class FakeProvider:
    def __init__(self, prices: dict[str, Decimal]) -> None:
        self.prices = prices
        self.calls: list[list[str]] = []

    async def fetch_latest_prices(self, provider_symbols: list[str]) -> ProviderQuoteBatch:
        self.calls.append(provider_symbols)
        return ProviderQuoteBatch(
            prices={
                symbol: self.prices[symbol] for symbol in provider_symbols if symbol in self.prices
            },
            unavailable_symbols=frozenset(
                symbol for symbol in provider_symbols if symbol not in self.prices
            ),
        )


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def test_quotes_serializes_success_and_partial_error(client: AsyncClient) -> None:
    service = StubQuoteService(
        QuoteResult(
            quotes=[
                Quote(
                    symbol="BTC/USD",
                    asset_class="CRYPTO",
                    provider="BINANCE_SPOT",
                    provider_symbol="BTCUSD",
                    price=Decimal("62373.79000000"),
                    volume=None,
                    provider_time=None,
                    received_at=datetime(2026, 6, 19, 10, 30, tzinfo=UTC),
                )
            ],
            errors=[
                QuoteError(
                    symbol="SOL/USD",
                    code="UNSUPPORTED_SYMBOL",
                    message="Symbol is not supported by this gateway.",
                )
            ],
        )
    )
    app.dependency_overrides[get_quote_service] = lambda: service

    response = await client.get("/v1/quotes", params={"symbols": "BTC/USD,SOL/USD"})

    assert response.status_code == 200
    assert service.requested == ["BTC/USD", "SOL/USD"]
    assert response.json() == {
        "quotes": [
            {
                "symbol": "BTC/USD",
                "price": "62373.79000000",
                "receivedAt": "2026-06-19T10:30:00Z",
            }
        ],
        "errors": [
            {
                "symbol": "SOL/USD",
                "code": "UNSUPPORTED_SYMBOL",
                "message": "Symbol is not supported by this gateway.",
            }
        ],
    }


@pytest.mark.parametrize("params", [None, {"symbols": ""}, {"symbols": " , "}])
async def test_quotes_rejects_invalid_symbols(
    client: AsyncClient,
    params: dict[str, str] | None,
) -> None:
    app.dependency_overrides[get_quote_service] = lambda: StubQuoteService()

    response = await client.get("/v1/quotes", params=params)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_SYMBOLS"


async def test_quotes_rejects_too_many_symbols(client: AsyncClient) -> None:
    app.dependency_overrides[get_quote_service] = lambda: StubQuoteService()
    app.dependency_overrides[get_settings] = lambda: Settings(max_quote_symbols=1)

    response = await client.get(
        "/v1/quotes",
        params={"symbols": "BTC/USD,ETH/USD"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "TOO_MANY_SYMBOLS"


async def test_quotes_returns_200_when_all_symbols_fail(client: AsyncClient) -> None:
    app.dependency_overrides[get_quote_service] = lambda: StubQuoteService(
        QuoteResult(
            quotes=[],
            errors=[
                QuoteError("SOL/USD", "UNSUPPORTED_SYMBOL", "Unsupported."),
            ],
        )
    )

    response = await client.get("/v1/quotes", params={"symbols": "SOL/USD"})

    assert response.status_code == 200
    assert response.json()["quotes"] == []
    assert response.json()["errors"][0]["code"] == "UNSUPPORTED_SYMBOL"


async def test_quotes_preserves_sanitized_database_failure(client: AsyncClient) -> None:
    app.dependency_overrides[get_quote_service] = lambda: StubQuoteService(
        error=DatabaseUnavailableError("postgresql://secret@database")
    )

    response = await client.get("/v1/quotes", params={"symbols": "BTC/USD"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "secret" not in response.text


async def test_quotes_routes_forex_through_twelvedata_provider_without_live_calls(
    client: AsyncClient,
) -> None:
    binance = FakeProvider({"BTCUSD": Decimal("62373.79")})
    twelvedata = FakeProvider({"EUR/USD": Decimal("1.14567")})
    app.dependency_overrides[get_quote_repository] = FakeSymbolRepository
    app.dependency_overrides[get_quote_provider] = lambda: QuoteProviderRouter(
        {"BINANCE_SPOT": binance, "TWELVE_DATA": twelvedata}
    )
    app.dependency_overrides[get_quote_cache] = QuoteCache

    response = await client.get(
        "/v1/quotes",
        params={"symbols": "EUR/USD,BTC/USD"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert [quote["symbol"] for quote in payload["quotes"]] == ["EUR/USD", "BTC/USD"]
    assert [quote["price"] for quote in payload["quotes"]] == ["1.14567", "62373.79"]
    assert all(set(quote) == {"symbol", "price", "receivedAt"} for quote in payload["quotes"])
    assert payload["errors"] == []
    assert binance.calls == [["BTCUSD"]]
    assert twelvedata.calls == [["EUR/USD"]]
