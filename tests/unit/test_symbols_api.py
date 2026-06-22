from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routes_symbols import get_symbol_service
from app.core.config import Settings, get_settings
from app.domain.errors import DatabaseUnavailableError
from app.domain.symbols import SupportedSymbol
from app.main import app


class StubSymbolService:
    def __init__(
        self,
        symbols: list[SupportedSymbol] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._symbols = symbols or []
        self._error = error

    async def list_supported_symbols(self) -> list[SupportedSymbol]:
        if self._error is not None:
            raise self._error
        return self._symbols


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def test_symbols_serializes_camel_case_fields_in_service_order(
    client: AsyncClient,
) -> None:
    app.dependency_overrides[get_symbol_service] = lambda: StubSymbolService(
        [
            SupportedSymbol(
                symbol="BTC/USD",
                asset_class="CRYPTO",
                provider="BINANCE_SPOT",
                provider_symbol="BTCUSD",
                enabled=True,
            ),
            SupportedSymbol(
                symbol="ETH/USD",
                asset_class="CRYPTO",
                provider="BINANCE_SPOT",
                provider_symbol="ETHUSD",
                enabled=True,
            ),
        ]
    )

    response = await client.get("/v1/symbols")

    assert response.status_code == 200
    assert response.json() == {
        "symbols": [
            {
                "symbol": "BTC/USD",
                "assetClass": "CRYPTO",
                "provider": "BINANCE_SPOT",
                "providerSymbol": "BTCUSD",
                "enabled": True,
            },
            {
                "symbol": "ETH/USD",
                "assetClass": "CRYPTO",
                "provider": "BINANCE_SPOT",
                "providerSymbol": "ETHUSD",
                "enabled": True,
            },
        ]
    }


async def test_symbols_returns_empty_list(client: AsyncClient) -> None:
    app.dependency_overrides[get_symbol_service] = lambda: StubSymbolService()

    response = await client.get("/v1/symbols")

    assert response.status_code == 200
    assert response.json() == {"symbols": []}


async def test_symbols_sanitizes_database_errors(client: AsyncClient) -> None:
    app.dependency_overrides[get_symbol_service] = lambda: StubSymbolService(
        error=DatabaseUnavailableError("postgresql://secret@database")
    )

    response = await client.get("/v1/symbols")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "DATABASE_UNAVAILABLE",
            "message": "The requested database-backed capability is temporarily unavailable.",
            "details": None,
        }
    }
    assert "secret" not in response.text


async def test_symbols_returns_503_without_database_configuration(
    client: AsyncClient,
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(database_url=None)

    response = await client.get("/v1/symbols")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"


async def test_health_remains_available_without_database_configuration(
    client: AsyncClient,
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(database_url=None)

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "UP"
