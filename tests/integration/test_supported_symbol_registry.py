import importlib.util
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.routes_quotes import get_quote_cache, get_quote_provider
from app.core.config import get_settings
from app.domain.quotes import ProviderQuoteBatch
from app.main import app

pytestmark = pytest.mark.integration


def load_migration_module() -> ModuleType:
    migration_path = (
        Path(__file__).parents[2] / "alembic" / "versions" / "20260619_0001_supported_symbols.py"
    )
    spec = importlib.util.spec_from_file_location("supported_symbols_migration", migration_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load supported-symbol migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_forex_migration_module() -> ModuleType:
    migration_path = (
        Path(__file__).parents[2] / "alembic" / "versions" / "20260622_0003_seed_forex_symbols.py"
    )
    spec = importlib.util.spec_from_file_location(
        "forex_supported_symbols_migration",
        migration_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load Forex supported-symbol migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_wti_etf_migration_module() -> ModuleType:
    migration_path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20260622_0007_seed_twelvedata_wti_etfs.py"
    )
    spec = importlib.util.spec_from_file_location(
        "wti_etf_supported_symbols_migration",
        migration_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load WTI and ETF supported-symbol migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_migration_creates_schema_and_exact_seed_mappings(
    database_engine: AsyncEngine,
) -> None:
    async with database_engine.connect() as connection:
        columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"]
                for column in inspect(sync_connection).get_columns("supported_symbols")
            }
        )
        constraints = await connection.run_sync(
            lambda sync_connection: {
                tuple(constraint["column_names"])
                for constraint in inspect(sync_connection).get_unique_constraints(
                    "supported_symbols"
                )
            }
        )
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT symbol, asset_class, provider, provider_symbol, enabled
                    FROM supported_symbols
                    ORDER BY symbol
                    """
                )
            )
        ).all()

    assert columns == {
        "id",
        "symbol",
        "asset_class",
        "provider",
        "provider_symbol",
        "enabled",
        "created_at",
        "updated_at",
    }
    assert ("symbol",) in constraints
    assert ("provider", "provider_symbol") in constraints
    assert rows == [
        ("AAPL", "US_STOCK", "TWELVE_DATA", "AAPL", True),
        ("AUD/USD", "FOREX", "TWELVE_DATA", "AUD/USD", True),
        ("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True),
        ("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True),
        ("ETH/USD", "CRYPTO", "BINANCE_SPOT", "ETHUSD", True),
        ("GBP/USD", "FOREX", "TWELVE_DATA", "GBP/USD", True),
        ("MSFT", "US_STOCK", "TWELVE_DATA", "MSFT", True),
        ("NVDA", "US_STOCK", "TWELVE_DATA", "NVDA", True),
        ("QQQ", "ETF", "TWELVE_DATA", "QQQ", True),
        ("SPY", "ETF", "TWELVE_DATA", "SPY", True),
        ("TSLA", "US_STOCK", "TWELVE_DATA", "TSLA", True),
        ("USD/JPY", "FOREX", "TWELVE_DATA", "USD/JPY", True),
        ("WTI", "COMMODITY", "TWELVE_DATA", "WTI", True),
        ("XAU/USD", "COMMODITY", "TWELVE_DATA", "XAU/USD", True),
    ]


async def test_seed_is_idempotent_and_restores_required_mapping(
    database_engine: AsyncEngine,
) -> None:
    migration = load_migration_module()
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE supported_symbols
                SET provider_symbol = 'OLD_BTC', enabled = false
                WHERE symbol = 'BTC/USD'
                """
            )
        )
        await connection.run_sync(migration.seed_supported_symbols)
        await connection.run_sync(migration.seed_supported_symbols)
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT symbol, provider_symbol, enabled
                    FROM supported_symbols
                    ORDER BY symbol
                    """
                )
            )
        ).all()

    assert rows == [
        ("AAPL", "AAPL", True),
        ("AUD/USD", "AUD/USD", True),
        ("BTC/USD", "BTCUSD", True),
        ("EUR/USD", "EUR/USD", True),
        ("ETH/USD", "ETHUSD", True),
        ("GBP/USD", "GBP/USD", True),
        ("MSFT", "MSFT", True),
        ("NVDA", "NVDA", True),
        ("QQQ", "QQQ", True),
        ("SPY", "SPY", True),
        ("TSLA", "TSLA", True),
        ("USD/JPY", "USD/JPY", True),
        ("WTI", "WTI", True),
        ("XAU/USD", "XAU/USD", True),
    ]


async def test_forex_seed_is_idempotent_and_preserves_crypto_mappings(
    database_engine: AsyncEngine,
) -> None:
    migration = load_forex_migration_module()
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE supported_symbols
                SET provider_symbol = 'OLD_EUR', enabled = false
                WHERE symbol = 'EUR/USD'
                """
            )
        )
        await connection.run_sync(migration.seed_forex_supported_symbols)
        await connection.run_sync(migration.seed_forex_supported_symbols)
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT symbol, asset_class, provider, provider_symbol, enabled
                    FROM supported_symbols
                    ORDER BY symbol
                    """
                )
            )
        ).all()

    assert rows == [
        ("AAPL", "US_STOCK", "TWELVE_DATA", "AAPL", True),
        ("AUD/USD", "FOREX", "TWELVE_DATA", "AUD/USD", True),
        ("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True),
        ("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True),
        ("ETH/USD", "CRYPTO", "BINANCE_SPOT", "ETHUSD", True),
        ("GBP/USD", "FOREX", "TWELVE_DATA", "GBP/USD", True),
        ("MSFT", "US_STOCK", "TWELVE_DATA", "MSFT", True),
        ("NVDA", "US_STOCK", "TWELVE_DATA", "NVDA", True),
        ("QQQ", "ETF", "TWELVE_DATA", "QQQ", True),
        ("SPY", "ETF", "TWELVE_DATA", "SPY", True),
        ("TSLA", "US_STOCK", "TWELVE_DATA", "TSLA", True),
        ("USD/JPY", "FOREX", "TWELVE_DATA", "USD/JPY", True),
        ("WTI", "COMMODITY", "TWELVE_DATA", "WTI", True),
        ("XAU/USD", "COMMODITY", "TWELVE_DATA", "XAU/USD", True),
    ]


async def test_wti_etf_seed_is_idempotent_and_preserves_existing_mappings(
    database_engine: AsyncEngine,
) -> None:
    migration = load_wti_etf_migration_module()
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE supported_symbols
                SET asset_class = 'OLD', provider_symbol = 'OLD_WTI', enabled = false
                WHERE symbol = 'WTI'
                """
            )
        )
        await connection.run_sync(migration.seed_twelvedata_wti_etf_symbols)
        await connection.run_sync(migration.seed_twelvedata_wti_etf_symbols)
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT symbol, asset_class, provider, provider_symbol, enabled
                    FROM supported_symbols
                    WHERE symbol IN ('WTI', 'SPY', 'QQQ')
                    ORDER BY symbol
                    """
                )
            )
        ).all()

    assert rows == [
        ("QQQ", "ETF", "TWELVE_DATA", "QQQ", True),
        ("SPY", "ETF", "TWELVE_DATA", "SPY", True),
        ("WTI", "COMMODITY", "TWELVE_DATA", "WTI", True),
    ]


async def test_wti_etf_downgrade_preserves_changed_mapping(
    database_engine: AsyncEngine,
) -> None:
    migration = load_wti_etf_migration_module()
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE supported_symbols
                SET provider_symbol = 'SPY_CUSTOM'
                WHERE symbol = 'SPY'
                """
            )
        )
        await connection.run_sync(migration.delete_twelvedata_wti_etf_symbols)
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT symbol, provider_symbol
                    FROM supported_symbols
                    WHERE symbol IN ('WTI', 'SPY', 'QQQ')
                    ORDER BY symbol
                    """
                )
            )
        ).all()

    assert rows == [("SPY", "SPY_CUSTOM")]


async def test_registry_constraints_reject_duplicate_provider_mapping(
    database_engine: AsyncEngine,
) -> None:
    with pytest.raises(IntegrityError):
        async with database_engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO supported_symbols
                        (symbol, asset_class, provider, provider_symbol, enabled)
                    VALUES
                        ('XBT/USD', 'CRYPTO', 'BINANCE_SPOT', 'BTCUSD', true)
                    """
                )
            )


async def test_api_lists_seed_symbols_in_canonical_order(
    database_engine: AsyncEngine,
) -> None:
    get_settings.cache_clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/symbols")

    assert response.status_code == 200
    assert [symbol["symbol"] for symbol in response.json()["symbols"]] == [
        "AAPL",
        "AUD/USD",
        "BTC/USD",
        "EUR/USD",
        "ETH/USD",
        "GBP/USD",
        "MSFT",
        "NVDA",
        "QQQ",
        "SPY",
        "TSLA",
        "USD/JPY",
        "WTI",
        "XAU/USD",
    ]


async def test_api_filters_disabled_rows_and_reflects_persisted_changes(
    database_engine: AsyncEngine,
) -> None:
    async with database_engine.begin() as connection:
        await connection.execute(
            text("UPDATE supported_symbols SET enabled = false WHERE symbol = 'ETH/USD'")
        )
        await connection.execute(
            text(
                """
                UPDATE supported_symbols
                SET provider_symbol = 'BTCUSD_TEST'
                WHERE symbol = 'BTC/USD'
                """
            )
        )

    get_settings.cache_clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/symbols")

    assert response.status_code == 200
    assert response.json() == {
        "symbols": [
            {
                "symbol": "AAPL",
                "assetClass": "US_STOCK",
                "provider": "TWELVE_DATA",
                "providerSymbol": "AAPL",
                "enabled": True,
            },
            {
                "symbol": "AUD/USD",
                "assetClass": "FOREX",
                "provider": "TWELVE_DATA",
                "providerSymbol": "AUD/USD",
                "enabled": True,
            },
            {
                "symbol": "BTC/USD",
                "assetClass": "CRYPTO",
                "provider": "BINANCE_SPOT",
                "providerSymbol": "BTCUSD_TEST",
                "enabled": True,
            },
            {
                "symbol": "EUR/USD",
                "assetClass": "FOREX",
                "provider": "TWELVE_DATA",
                "providerSymbol": "EUR/USD",
                "enabled": True,
            },
            {
                "symbol": "GBP/USD",
                "assetClass": "FOREX",
                "provider": "TWELVE_DATA",
                "providerSymbol": "GBP/USD",
                "enabled": True,
            },
            {
                "symbol": "MSFT",
                "assetClass": "US_STOCK",
                "provider": "TWELVE_DATA",
                "providerSymbol": "MSFT",
                "enabled": True,
            },
            {
                "symbol": "NVDA",
                "assetClass": "US_STOCK",
                "provider": "TWELVE_DATA",
                "providerSymbol": "NVDA",
                "enabled": True,
            },
            {
                "symbol": "QQQ",
                "assetClass": "ETF",
                "provider": "TWELVE_DATA",
                "providerSymbol": "QQQ",
                "enabled": True,
            },
            {
                "symbol": "SPY",
                "assetClass": "ETF",
                "provider": "TWELVE_DATA",
                "providerSymbol": "SPY",
                "enabled": True,
            },
            {
                "symbol": "TSLA",
                "assetClass": "US_STOCK",
                "provider": "TWELVE_DATA",
                "providerSymbol": "TSLA",
                "enabled": True,
            },
            {
                "symbol": "USD/JPY",
                "assetClass": "FOREX",
                "provider": "TWELVE_DATA",
                "providerSymbol": "USD/JPY",
                "enabled": True,
            },
            {
                "symbol": "WTI",
                "assetClass": "COMMODITY",
                "provider": "TWELVE_DATA",
                "providerSymbol": "WTI",
                "enabled": True,
            },
            {
                "symbol": "XAU/USD",
                "assetClass": "COMMODITY",
                "provider": "TWELVE_DATA",
                "providerSymbol": "XAU/USD",
                "enabled": True,
            },
        ]
    }


async def test_quotes_use_persisted_provider_mapping(
    database_engine: AsyncEngine,
) -> None:
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE supported_symbols
                SET provider_symbol = 'BTCUSD_TEST'
                WHERE symbol = 'BTC/USD'
                """
            )
        )

    class FakeProvider:
        def __init__(self) -> None:
            self.requested_provider_symbols: list[str] = []

        async def fetch_latest_prices(
            self,
            provider_symbols: list[str],
        ) -> ProviderQuoteBatch:
            self.requested_provider_symbols.extend(provider_symbols)
            return ProviderQuoteBatch(
                prices={"BTCUSD_TEST": Decimal("123.4500")},
                unavailable_symbols=frozenset(),
            )

    provider = FakeProvider()
    app.dependency_overrides[get_quote_provider] = lambda: provider
    get_quote_cache.cache_clear()
    get_settings.cache_clear()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/v1/quotes",
                params={"symbols": "BTC/USD"},
            )
    finally:
        app.dependency_overrides.clear()
        get_quote_cache.cache_clear()

    assert response.status_code == 200
    assert provider.requested_provider_symbols == ["BTCUSD_TEST"]
    quote = response.json()["quotes"][0]
    assert set(quote) == {"symbol", "price", "receivedAt"}
    assert quote["symbol"] == "BTC/USD"
    assert quote["price"] == "123.4500"
    assert quote["receivedAt"].endswith("Z")
