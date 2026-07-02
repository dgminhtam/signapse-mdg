from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routes_historical_price import get_historical_price_service
from app.domain.errors import (
    CandleRequestError,
    DatabaseUnavailableError,
    HistoricalPriceNotFoundError,
    ProviderUnavailableError,
)
from app.main import app
from app.services.historical_prices import HistoricalPriceRequest, HistoricalPriceResult

START = datetime(2026, 6, 19, 10, 30, tzinfo=UTC)


class StubHistoricalPriceService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.requested: HistoricalPriceRequest | None = None

    async def get_historical_price(
        self,
        request: HistoricalPriceRequest,
    ) -> HistoricalPriceResult:
        self.requested = request
        if self.error is not None:
            raise self.error
        return HistoricalPriceResult("BTC/USD", Decimal("104250.12"), START)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def test_historical_price_serializes_minimal_contract(client: AsyncClient) -> None:
    service = StubHistoricalPriceService()
    app.dependency_overrides[get_historical_price_service] = lambda: service

    response = await client.get(
        "/v1/historical-price",
        params={"symbol": "BTC/USD", "at": "2026-06-19T10:30:12Z"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "symbol": "BTC/USD",
        "price": "104250.12",
        "pricedAt": "2026-06-19T10:30:00Z",
    }
    assert service.requested == HistoricalPriceRequest(
        "BTC/USD",
        datetime(2026, 6, 19, 10, 30, 12, tzinfo=UTC),
    )
    assert "timeframe" not in response.text
    assert "provider" not in response.text


@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({"at": "2026-06-19T10:30:12Z"}, "UNSUPPORTED_SYMBOL"),
        ({"symbol": "BTC/USD"}, "INVALID_TIME_RANGE"),
        ({"symbol": "BTC/USD", "at": "bad"}, "INVALID_TIME_RANGE"),
    ],
)
async def test_historical_price_returns_contract_400_not_422(
    client: AsyncClient,
    params: dict[str, str],
    code: str,
) -> None:
    app.dependency_overrides[get_historical_price_service] = lambda: StubHistoricalPriceService()

    response = await client.get("/v1/historical-price", params=params)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (
            CandleRequestError(
                "UNSUPPORTED_SYMBOL",
                "Symbol is not supported by this gateway.",
                {"symbol": "SOL/USD"},
            ),
            400,
            "UNSUPPORTED_SYMBOL",
        ),
        (HistoricalPriceNotFoundError(), 404, "PRICE_NOT_FOUND"),
        (DatabaseUnavailableError("postgresql://secret"), 503, "DATABASE_UNAVAILABLE"),
        (ProviderUnavailableError("raw provider payload"), 503, "PROVIDER_UNAVAILABLE"),
    ],
)
async def test_historical_price_sanitizes_service_failures(
    client: AsyncClient,
    error: Exception,
    status: int,
    code: str,
) -> None:
    app.dependency_overrides[get_historical_price_service] = lambda: StubHistoricalPriceService(
        error
    )

    response = await client.get(
        "/v1/historical-price",
        params={"symbol": "BTC/USD", "at": "2026-06-19T10:30:12Z"},
    )

    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "secret" not in response.text
    assert "raw provider payload" not in response.text


async def test_historical_price_does_not_require_public_timeframe(client: AsyncClient) -> None:
    app.dependency_overrides[get_historical_price_service] = lambda: StubHistoricalPriceService()

    response = await client.get(
        "/v1/historical-price",
        params={"symbol": "BTC/USD", "at": "2026-06-19T10:30:12Z"},
    )

    assert response.status_code == 200
    assert set(response.json()) == {"symbol", "price", "pricedAt"}
