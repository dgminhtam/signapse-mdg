import importlib.util
from asyncio import to_thread
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import command
from app.api.routes_quotes import get_quote_cache, get_quote_provider
from app.core.config import get_settings
from app.domain.quotes import ProviderQuoteBatch
from app.domain.symbols import SupportedSymbol
from app.main import app

pytestmark = pytest.mark.integration

# Exercise the historical registry and its migrations at their original boundary.
MIGRATION_TARGET = "20260727_0020"


async def use_legacy_registry_schema() -> None:
    await to_thread(command.downgrade, Config("alembic.ini"), "20260727_0019")


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


def load_yfinance_migration_module() -> ModuleType:
    migration_path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20260622_0008_seed_yfinance_symbols.py"
    )
    spec = importlib.util.spec_from_file_location(
        "yfinance_supported_symbols_migration",
        migration_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load yfinance supported-symbol migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_crypto_migration_module() -> ModuleType:
    migration_path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20260629_0009_move_crypto_to_twelvedata.py"
    )
    spec = importlib.util.spec_from_file_location(
        "crypto_twelvedata_supported_symbols_migration",
        migration_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load crypto Twelve Data supported-symbol migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_inline_symbol_calendar_config_migration_module() -> ModuleType:
    migration_path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20260630_0012_inline_symbol_calendar_config.py"
    )
    spec = importlib.util.spec_from_file_location(
        "inline_symbol_calendar_config_migration",
        migration_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load inline symbol calendar config migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_migration_creates_schema_and_exact_seed_mappings(
    database_engine: AsyncEngine,
) -> None:
    async with database_engine.connect() as connection:
        columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"]: column
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
        check_constraints = await connection.run_sync(
            lambda sync_connection: {
                constraint["name"]
                for constraint in inspect(sync_connection).get_check_constraints(
                    "supported_symbols"
                )
            }
        )
        display_rows = (
            await connection.execute(
                text(
                    """
                    SELECT symbol, price_display_decimals
                    FROM supported_symbols
                    ORDER BY symbol
                    """
                )
            )
        ).all()
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT
                        supported_symbols.symbol,
                        supported_symbols.asset_class,
                        symbol_provider_mappings.provider,
                        symbol_provider_mappings.provider_symbol,
                        supported_symbols.enabled
                    FROM supported_symbols
                    JOIN symbol_provider_mappings
                      ON symbol_provider_mappings.supported_symbol_id = supported_symbols.id
                     AND symbol_provider_mappings.is_active
                    ORDER BY symbol
                    """
                )
            )
        ).all()

    assert set(columns) == {
        "id",
        "symbol",
        "asset_class",
        "calendar_source",
        "calendar_name",
        "calendar_timezone",
        "price_display_decimals",
        "enabled",
        "created_at",
        "updated_at",
    }
    assert ("symbol",) in constraints
    assert ("provider", "provider_symbol") not in constraints
    assert columns["price_display_decimals"]["nullable"] is False
    assert columns["price_display_decimals"]["default"] is None
    assert "ck_supported_symbols_price_display_decimals" in check_constraints
    assert {symbol for symbol, decimals in display_rows if decimals == 5} == {
        "AUD/USD",
        "EUR/USD",
        "GBP/USD",
    }
    assert {symbol for symbol, decimals in display_rows if decimals == 3} == {
        "NATGAS",
        "USD/JPY",
        "XAG/USD",
    }
    assert {symbol for symbol, decimals in display_rows if decimals == 2} == {
        "AAPL",
        "BRENT",
        "BTC/USD",
        "COFFEE",
        "CORN",
        "DJI",
        "ETH/USD",
        "MSFT",
        "NDX",
        "NVDA",
        "QQQ",
        "SPX",
        "SPY",
        "SUGAR",
        "TSLA",
        "WHEAT",
        "WTI",
        "XAU/USD",
    }
    assert len(display_rows) == 24
    assert rows == [
        ("AAPL", "US_STOCK", "TWELVE_DATA", "AAPL", True),
        ("AUD/USD", "FOREX", "YFINANCE", "AUDUSD=X", True),
        ("BRENT", "COMMODITY", "YFINANCE", "BZ=F", True),
        ("BTC/USD", "CRYPTO", "TWELVE_DATA", "BTC/USD", True),
        ("COFFEE", "COMMODITY", "YFINANCE", "KC=F", True),
        ("CORN", "COMMODITY", "YFINANCE", "ZC=F", True),
        ("DJI", "STOCK_INDEX", "YFINANCE", "^DJI", True),
        ("ETH/USD", "CRYPTO", "BINANCE_SPOT", "ETHUSD", True),
        ("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True),
        ("GBP/USD", "FOREX", "YFINANCE", "GBPUSD=X", True),
        ("MSFT", "US_STOCK", "YFINANCE", "MSFT", True),
        ("NATGAS", "COMMODITY", "YFINANCE", "NG=F", True),
        ("NDX", "STOCK_INDEX", "YFINANCE", "^NDX", True),
        ("NVDA", "US_STOCK", "YFINANCE", "NVDA", True),
        ("QQQ", "ETF", "TWELVE_DATA", "QQQ", True),
        ("SPX", "STOCK_INDEX", "YFINANCE", "^GSPC", True),
        ("SPY", "ETF", "YFINANCE", "SPY", True),
        ("SUGAR", "COMMODITY", "YFINANCE", "SB=F", True),
        ("TSLA", "US_STOCK", "YFINANCE", "TSLA", True),
        ("USD/JPY", "FOREX", "YFINANCE", "JPY=X", True),
        ("WHEAT", "COMMODITY", "YFINANCE", "ZW=F", True),
        ("WTI", "COMMODITY", "YFINANCE", "CL=F", True),
        ("XAG/USD", "COMMODITY", "YFINANCE", "SI=F", True),
        ("XAU/USD", "COMMODITY", "TWELVE_DATA", "XAU/USD", True),
    ]


async def test_inline_calendar_config_migration_has_expected_schema_and_seed_data(
    database_engine: AsyncEngine,
) -> None:
    async with database_engine.connect() as connection:
        table_names = await connection.run_sync(
            lambda sync_connection: set(inspect(sync_connection).get_table_names())
        )
        columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"]: column
                for column in inspect(sync_connection).get_columns("supported_symbols")
            }
        )
        configs = (
            await connection.execute(
                text(
                    """
                    SELECT symbol, calendar_source, calendar_name, calendar_timezone
                    FROM supported_symbols
                    WHERE calendar_source IS NOT NULL
                    ORDER BY symbol
                    """
                )
            )
        ).all()

    assert "market_calendars" not in table_names
    assert "market_calendar_sessions" not in table_names
    assert "calendar_code" not in columns
    assert {"calendar_source", "calendar_name", "calendar_timezone"} <= columns.keys()
    assert configs == [
        ("AAPL", "pandas_market_calendars", "NYSE", "America/New_York"),
        ("AUD/USD", "pandas_market_calendars", "FOREX", "America/New_York"),
        ("BRENT", "pandas_market_calendars", "CMEGlobex_Energy", "America/New_York"),
        ("BTC/USD", "internal", "24/7", "UTC"),
        ("COFFEE", "pandas_market_calendars", "ICEUS", "America/New_York"),
        ("CORN", "pandas_market_calendars", "CMEGlobex_Grains", "America/Chicago"),
        ("DJI", "pandas_market_calendars", "NYSE", "America/New_York"),
        ("ETH/USD", "internal", "24/7", "UTC"),
        ("EUR/USD", "pandas_market_calendars", "FOREX", "America/New_York"),
        ("GBP/USD", "pandas_market_calendars", "FOREX", "America/New_York"),
        ("MSFT", "pandas_market_calendars", "NYSE", "America/New_York"),
        ("NATGAS", "pandas_market_calendars", "CMEGlobex_Energy", "America/New_York"),
        ("NDX", "pandas_market_calendars", "NYSE", "America/New_York"),
        ("NVDA", "pandas_market_calendars", "NYSE", "America/New_York"),
        ("QQQ", "pandas_market_calendars", "NYSE", "America/New_York"),
        ("SPX", "pandas_market_calendars", "NYSE", "America/New_York"),
        ("SPY", "pandas_market_calendars", "NYSE", "America/New_York"),
        ("SUGAR", "pandas_market_calendars", "ICEUS", "America/New_York"),
        ("TSLA", "pandas_market_calendars", "NYSE", "America/New_York"),
        ("USD/JPY", "pandas_market_calendars", "FOREX", "America/New_York"),
        ("WHEAT", "pandas_market_calendars", "CMEGlobex_Grains", "America/Chicago"),
        ("WTI", "pandas_market_calendars", "CMEGlobex_Energy", "America/New_York"),
        ("XAG/USD", "pandas_market_calendars", "CMEGlobex_Metals", "America/New_York"),
        ("XAU/USD", "pandas_market_calendars", "FOREX", "America/New_York"),
    ]


async def test_inline_calendar_config_seed_helper_is_idempotent(
    database_engine: AsyncEngine,
) -> None:
    migration = load_inline_symbol_calendar_config_migration_module()
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE supported_symbols
                SET calendar_source = NULL,
                    calendar_name = NULL,
                    calendar_timezone = NULL
                WHERE symbol = 'SPY'
                """
            )
        )
        await connection.run_sync(migration.seed_inline_calendar_config)
        await connection.run_sync(migration.seed_inline_calendar_config)
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT symbol, calendar_source, calendar_name, calendar_timezone
                    FROM supported_symbols
                    WHERE symbol = 'SPY'
                    """
                )
            )
        ).all()

    assert rows == [("SPY", "pandas_market_calendars", "NYSE", "America/New_York")]


async def test_seed_is_idempotent_and_restores_required_mapping(
    database_engine: AsyncEngine,
) -> None:
    await use_legacy_registry_schema()
    migration = load_migration_module()
    async with database_engine.begin() as connection:
        await connection.execute(
            text("ALTER TABLE supported_symbols ALTER COLUMN price_display_decimals SET DEFAULT 2")
        )
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
        await connection.execute(
            text("ALTER TABLE supported_symbols ALTER COLUMN price_display_decimals DROP DEFAULT")
        )

    assert rows == [
        ("AAPL", "AAPL", True),
        ("AUD/USD", "AUDUSD=X", True),
        ("BRENT", "BZ=F", True),
        ("BTC/USD", "BTCUSD", True),
        ("COFFEE", "KC=F", True),
        ("CORN", "ZC=F", True),
        ("DJI", "^DJI", True),
        ("ETH/USD", "ETHUSD", True),
        ("EUR/USD", "EUR/USD", True),
        ("GBP/USD", "GBPUSD=X", True),
        ("MSFT", "MSFT", True),
        ("NATGAS", "NG=F", True),
        ("NDX", "^NDX", True),
        ("NVDA", "NVDA", True),
        ("QQQ", "QQQ", True),
        ("SPX", "^GSPC", True),
        ("SPY", "SPY", True),
        ("SUGAR", "SB=F", True),
        ("TSLA", "TSLA", True),
        ("USD/JPY", "JPY=X", True),
        ("WHEAT", "ZW=F", True),
        ("WTI", "CL=F", True),
        ("XAG/USD", "SI=F", True),
        ("XAU/USD", "XAU/USD", True),
    ]


async def test_forex_seed_is_idempotent_and_preserves_crypto_mappings(
    database_engine: AsyncEngine,
) -> None:
    await use_legacy_registry_schema()
    migration = load_forex_migration_module()
    async with database_engine.begin() as connection:
        await connection.execute(
            text("ALTER TABLE supported_symbols ALTER COLUMN price_display_decimals SET DEFAULT 2")
        )
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
        await connection.execute(
            text("ALTER TABLE supported_symbols ALTER COLUMN price_display_decimals DROP DEFAULT")
        )

    assert rows == [
        ("AAPL", "US_STOCK", "TWELVE_DATA", "AAPL", True),
        ("AUD/USD", "FOREX", "TWELVE_DATA", "AUD/USD", True),
        ("BRENT", "COMMODITY", "YFINANCE", "BZ=F", True),
        ("BTC/USD", "CRYPTO", "TWELVE_DATA", "BTC/USD", True),
        ("COFFEE", "COMMODITY", "YFINANCE", "KC=F", True),
        ("CORN", "COMMODITY", "YFINANCE", "ZC=F", True),
        ("DJI", "STOCK_INDEX", "YFINANCE", "^DJI", True),
        ("ETH/USD", "CRYPTO", "BINANCE_SPOT", "ETHUSD", True),
        ("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True),
        ("GBP/USD", "FOREX", "TWELVE_DATA", "GBP/USD", True),
        ("MSFT", "US_STOCK", "YFINANCE", "MSFT", True),
        ("NATGAS", "COMMODITY", "YFINANCE", "NG=F", True),
        ("NDX", "STOCK_INDEX", "YFINANCE", "^NDX", True),
        ("NVDA", "US_STOCK", "YFINANCE", "NVDA", True),
        ("QQQ", "ETF", "TWELVE_DATA", "QQQ", True),
        ("SPX", "STOCK_INDEX", "YFINANCE", "^GSPC", True),
        ("SPY", "ETF", "YFINANCE", "SPY", True),
        ("SUGAR", "COMMODITY", "YFINANCE", "SB=F", True),
        ("TSLA", "US_STOCK", "YFINANCE", "TSLA", True),
        ("USD/JPY", "FOREX", "TWELVE_DATA", "USD/JPY", True),
        ("WHEAT", "COMMODITY", "YFINANCE", "ZW=F", True),
        ("WTI", "COMMODITY", "YFINANCE", "CL=F", True),
        ("XAG/USD", "COMMODITY", "YFINANCE", "SI=F", True),
        ("XAU/USD", "COMMODITY", "TWELVE_DATA", "XAU/USD", True),
    ]


async def test_wti_etf_seed_is_idempotent_and_preserves_existing_mappings(
    database_engine: AsyncEngine,
) -> None:
    await use_legacy_registry_schema()
    migration = load_wti_etf_migration_module()
    async with database_engine.begin() as connection:
        await connection.execute(
            text("ALTER TABLE supported_symbols ALTER COLUMN price_display_decimals SET DEFAULT 2")
        )
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
        await connection.execute(
            text("ALTER TABLE supported_symbols ALTER COLUMN price_display_decimals DROP DEFAULT")
        )

    assert rows == [
        ("QQQ", "ETF", "TWELVE_DATA", "QQQ", True),
        ("SPY", "ETF", "TWELVE_DATA", "SPY", True),
        ("WTI", "COMMODITY", "TWELVE_DATA", "WTI", True),
    ]


async def test_wti_etf_downgrade_preserves_changed_mapping(
    database_engine: AsyncEngine,
) -> None:
    await use_legacy_registry_schema()
    migration = load_wti_etf_migration_module()
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE supported_symbols
                SET provider_symbol = CASE symbol
                    WHEN 'QQQ' THEN 'QQQ_CUSTOM'
                    ELSE 'SPY_CUSTOM'
                END
                WHERE symbol IN ('QQQ', 'SPY')
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

    assert rows == [
        ("QQQ", "QQQ_CUSTOM"),
        ("SPY", "SPY_CUSTOM"),
        ("WTI", "CL=F"),
    ]


async def test_yfinance_seed_is_idempotent_and_preserves_existing_mappings(
    database_engine: AsyncEngine,
) -> None:
    await use_legacy_registry_schema()
    migration = load_yfinance_migration_module()
    async with database_engine.begin() as connection:
        await connection.execute(
            text("ALTER TABLE supported_symbols ALTER COLUMN price_display_decimals SET DEFAULT 2")
        )
        await connection.execute(
            text(
                """
                UPDATE supported_symbols
                SET asset_class = 'OLD', provider_symbol = 'OLD_SPX', enabled = false
                WHERE symbol = 'SPX'
                """
            )
        )
        await connection.run_sync(migration.seed_yfinance_supported_symbols)
        await connection.run_sync(migration.seed_yfinance_supported_symbols)
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT symbol, asset_class, provider, provider_symbol, enabled
                    FROM supported_symbols
                    WHERE provider = 'YFINANCE'
                    ORDER BY symbol
                    """
                )
            )
        ).all()
        existing = (
            await connection.execute(
                text(
                    """
                    SELECT symbol, asset_class, provider, provider_symbol, enabled
                    FROM supported_symbols
                    WHERE symbol IN ('BTC/USD', 'EUR/USD', 'WTI', 'SPY')
                    ORDER BY symbol
                    """
                )
            )
        ).all()
        await connection.execute(
            text("ALTER TABLE supported_symbols ALTER COLUMN price_display_decimals DROP DEFAULT")
        )

    assert rows == [
        ("AUD/USD", "FOREX", "YFINANCE", "AUDUSD=X", True),
        ("BRENT", "COMMODITY", "YFINANCE", "BZ=F", True),
        ("COFFEE", "COMMODITY", "YFINANCE", "KC=F", True),
        ("CORN", "COMMODITY", "YFINANCE", "ZC=F", True),
        ("DJI", "STOCK_INDEX", "YFINANCE", "^DJI", True),
        ("GBP/USD", "FOREX", "YFINANCE", "GBPUSD=X", True),
        ("MSFT", "US_STOCK", "YFINANCE", "MSFT", True),
        ("NATGAS", "COMMODITY", "YFINANCE", "NG=F", True),
        ("NDX", "STOCK_INDEX", "YFINANCE", "^NDX", True),
        ("NVDA", "US_STOCK", "YFINANCE", "NVDA", True),
        ("SPX", "STOCK_INDEX", "YFINANCE", "^GSPC", True),
        ("SPY", "ETF", "YFINANCE", "SPY", True),
        ("SUGAR", "COMMODITY", "YFINANCE", "SB=F", True),
        ("TSLA", "US_STOCK", "YFINANCE", "TSLA", True),
        ("USD/JPY", "FOREX", "YFINANCE", "JPY=X", True),
        ("WHEAT", "COMMODITY", "YFINANCE", "ZW=F", True),
        ("WTI", "COMMODITY", "YFINANCE", "CL=F", True),
        ("XAG/USD", "COMMODITY", "YFINANCE", "SI=F", True),
    ]
    assert existing == [
        ("BTC/USD", "CRYPTO", "TWELVE_DATA", "BTC/USD", True),
        ("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True),
        ("SPY", "ETF", "YFINANCE", "SPY", True),
        ("WTI", "COMMODITY", "YFINANCE", "CL=F", True),
    ]


async def test_yfinance_downgrade_preserves_changed_mapping(
    database_engine: AsyncEngine,
) -> None:
    await use_legacy_registry_schema()
    migration = load_yfinance_migration_module()
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE supported_symbols
                SET provider_symbol = provider_symbol || '_CUSTOM'
                WHERE provider = 'YFINANCE'
                """
            )
        )
        await connection.run_sync(migration.delete_yfinance_supported_symbols)
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT symbol, provider_symbol
                    FROM supported_symbols
                    WHERE symbol = 'SPX'
                    """
                )
            )
        ).all()

    assert rows == [("SPX", "^GSPC_CUSTOM")]


async def test_crypto_twelvedata_migration_is_idempotent_and_downgrades(
    database_engine: AsyncEngine,
) -> None:
    await use_legacy_registry_schema()
    migration = load_crypto_migration_module()
    async with database_engine.begin() as connection:
        await connection.execute(
            text("ALTER TABLE supported_symbols ALTER COLUMN price_display_decimals SET DEFAULT 2")
        )
        await connection.execute(
            text(
                """
                UPDATE supported_symbols
                SET provider = 'BINANCE_SPOT', provider_symbol = 'OLD_BTC', enabled = false
                WHERE symbol = 'BTC/USD'
                """
            )
        )
        await connection.run_sync(
            lambda sync_connection: migration.upsert_crypto_symbols(
                sync_connection,
                migration.TWELVEDATA_CRYPTO_SYMBOLS,
            )
        )
        await connection.run_sync(
            lambda sync_connection: migration.upsert_crypto_symbols(
                sync_connection,
                migration.TWELVEDATA_CRYPTO_SYMBOLS,
            )
        )
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT symbol, asset_class, provider, provider_symbol, enabled
                    FROM supported_symbols
                    WHERE symbol IN ('BTC/USD', 'ETH/USD')
                    ORDER BY symbol
                    """
                )
            )
        ).all()
        await connection.run_sync(
            lambda sync_connection: migration.upsert_crypto_symbols(
                sync_connection,
                migration.BINANCE_CRYPTO_SYMBOLS,
            )
        )
        rollback_rows = (
            await connection.execute(
                text(
                    """
                    SELECT symbol, provider, provider_symbol, enabled
                    FROM supported_symbols
                    WHERE symbol IN ('BTC/USD', 'ETH/USD')
                    ORDER BY symbol
                    """
                )
            )
        ).all()
        await connection.execute(
            text("ALTER TABLE supported_symbols ALTER COLUMN price_display_decimals DROP DEFAULT")
        )

    assert rows == [
        ("BTC/USD", "CRYPTO", "TWELVE_DATA", "BTC/USD", True),
        ("ETH/USD", "CRYPTO", "TWELVE_DATA", "ETH/USD", True),
    ]
    assert rollback_rows == [
        ("BTC/USD", "BINANCE_SPOT", "BTCUSD", True),
        ("ETH/USD", "BINANCE_SPOT", "ETHUSD", True),
    ]


async def test_registry_constraints_reject_duplicate_provider_mapping(
    database_engine: AsyncEngine,
) -> None:
    with pytest.raises(IntegrityError):
        async with database_engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    WITH inserted_symbol AS (
                        INSERT INTO supported_symbols (
                            symbol,
                            asset_class,
                            enabled,
                            price_display_decimals
                        )
                        VALUES ('XBT/USD', 'CRYPTO', true, 2)
                        RETURNING id
                    )
                    INSERT INTO symbol_provider_mappings (
                        supported_symbol_id,
                        provider,
                        provider_symbol,
                        is_active
                    )
                    SELECT id, 'TWELVE_DATA', 'BTC/USD', true
                    FROM inserted_symbol
                    """
                )
            )


@pytest.mark.parametrize("price_display_decimals", [None, -1, 19])
async def test_registry_rejects_invalid_price_display_decimals(
    database_engine: AsyncEngine,
    price_display_decimals: int | None,
) -> None:
    with pytest.raises(IntegrityError):
        async with database_engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO supported_symbols (
                        symbol,
                        asset_class,
                        enabled,
                        price_display_decimals
                    )
                    VALUES (
                        'TEST/USD',
                        'FOREX',
                        true,
                        :price_display_decimals
                    )
                    """
                ),
                {"price_display_decimals": price_display_decimals},
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
        "BRENT",
        "BTC/USD",
        "COFFEE",
        "CORN",
        "DJI",
        "ETH/USD",
        "EUR/USD",
        "GBP/USD",
        "MSFT",
        "NATGAS",
        "NDX",
        "NVDA",
        "QQQ",
        "SPX",
        "SPY",
        "SUGAR",
        "TSLA",
        "USD/JPY",
        "WHEAT",
        "WTI",
        "XAG/USD",
        "XAU/USD",
    ]


async def test_api_exposes_all_mappings_in_default_first_order(
    database_engine: AsyncEngine,
) -> None:
    get_settings.cache_clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/symbols")

    assert response.status_code == 200
    aapl = next(item for item in response.json()["symbols"] if item["symbol"] == "AAPL")
    assert aapl["provider"] == "TWELVE_DATA"
    assert aapl["providerMappings"] == [
        {
            "provider": "TWELVE_DATA",
            "providerSymbol": "AAPL",
            "isDefault": True,
        },
        {
            "provider": "YFINANCE",
            "providerSymbol": "AAPL",
            "isDefault": False,
        },
    ]


async def test_api_fails_closed_when_enabled_asset_lacks_default_mapping(
    database_engine: AsyncEngine,
) -> None:
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE symbol_provider_mappings
                SET is_active = false
                WHERE supported_symbol_id = (
                    SELECT id FROM supported_symbols WHERE symbol = 'AAPL'
                )
                """
            )
        )

    try:
        get_settings.cache_clear()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/v1/quotes",
                params={"symbols": "AAPL", "provider": "YFINANCE"},
            )

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    finally:
        async with database_engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE symbol_provider_mappings
                    SET is_active = true
                    WHERE supported_symbol_id = (
                        SELECT id FROM supported_symbols WHERE symbol = 'AAPL'
                    )
                      AND provider = 'TWELVE_DATA'
                    """
                )
            )


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
                UPDATE symbol_provider_mappings
                SET provider_symbol = 'BTC/USD_TEST'
                WHERE supported_symbol_id = (
                    SELECT id FROM supported_symbols WHERE symbol = 'BTC/USD'
                )
                  AND is_active
                """
            )
        )

    get_settings.cache_clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/symbols")

    assert response.status_code == 200
    symbols = response.json()["symbols"]
    assert {symbol["symbol"]: symbol.pop("priceDisplayDecimals") for symbol in symbols} == {
        "AAPL": 2,
        "AUD/USD": 5,
        "BRENT": 2,
        "BTC/USD": 2,
        "COFFEE": 2,
        "CORN": 2,
        "DJI": 2,
        "EUR/USD": 5,
        "GBP/USD": 5,
        "MSFT": 2,
        "NATGAS": 3,
        "NDX": 2,
        "NVDA": 2,
        "QQQ": 2,
        "SPX": 2,
        "SPY": 2,
        "SUGAR": 2,
        "TSLA": 2,
        "USD/JPY": 3,
        "WHEAT": 2,
        "WTI": 2,
        "XAG/USD": 3,
        "XAU/USD": 2,
    }
    assert all(
        symbol["providerMappings"]
        and symbol["providerMappings"][0]["isDefault"]
        and all(
            "provider" in mapping and "providerSymbol" in mapping
            for mapping in symbol["providerMappings"]
        )
        for symbol in symbols
    )
    for symbol in symbols:
        symbol.pop("providerMappings")
    assert {"symbols": symbols} == {
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
                "provider": "YFINANCE",
                "providerSymbol": "AUDUSD=X",
                "enabled": True,
            },
            {
                "symbol": "BRENT",
                "assetClass": "COMMODITY",
                "provider": "YFINANCE",
                "providerSymbol": "BZ=F",
                "enabled": True,
            },
            {
                "symbol": "BTC/USD",
                "assetClass": "CRYPTO",
                "provider": "TWELVE_DATA",
                "providerSymbol": "BTC/USD_TEST",
                "enabled": True,
            },
            {
                "symbol": "COFFEE",
                "assetClass": "COMMODITY",
                "provider": "YFINANCE",
                "providerSymbol": "KC=F",
                "enabled": True,
            },
            {
                "symbol": "CORN",
                "assetClass": "COMMODITY",
                "provider": "YFINANCE",
                "providerSymbol": "ZC=F",
                "enabled": True,
            },
            {
                "symbol": "DJI",
                "assetClass": "STOCK_INDEX",
                "provider": "YFINANCE",
                "providerSymbol": "^DJI",
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
                "provider": "YFINANCE",
                "providerSymbol": "GBPUSD=X",
                "enabled": True,
            },
            {
                "symbol": "MSFT",
                "assetClass": "US_STOCK",
                "provider": "YFINANCE",
                "providerSymbol": "MSFT",
                "enabled": True,
            },
            {
                "symbol": "NATGAS",
                "assetClass": "COMMODITY",
                "provider": "YFINANCE",
                "providerSymbol": "NG=F",
                "enabled": True,
            },
            {
                "symbol": "NDX",
                "assetClass": "STOCK_INDEX",
                "provider": "YFINANCE",
                "providerSymbol": "^NDX",
                "enabled": True,
            },
            {
                "symbol": "NVDA",
                "assetClass": "US_STOCK",
                "provider": "YFINANCE",
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
                "symbol": "SPX",
                "assetClass": "STOCK_INDEX",
                "provider": "YFINANCE",
                "providerSymbol": "^GSPC",
                "enabled": True,
            },
            {
                "symbol": "SPY",
                "assetClass": "ETF",
                "provider": "YFINANCE",
                "providerSymbol": "SPY",
                "enabled": True,
            },
            {
                "symbol": "SUGAR",
                "assetClass": "COMMODITY",
                "provider": "YFINANCE",
                "providerSymbol": "SB=F",
                "enabled": True,
            },
            {
                "symbol": "TSLA",
                "assetClass": "US_STOCK",
                "provider": "YFINANCE",
                "providerSymbol": "TSLA",
                "enabled": True,
            },
            {
                "symbol": "USD/JPY",
                "assetClass": "FOREX",
                "provider": "YFINANCE",
                "providerSymbol": "JPY=X",
                "enabled": True,
            },
            {
                "symbol": "WHEAT",
                "assetClass": "COMMODITY",
                "provider": "YFINANCE",
                "providerSymbol": "ZW=F",
                "enabled": True,
            },
            {
                "symbol": "WTI",
                "assetClass": "COMMODITY",
                "provider": "YFINANCE",
                "providerSymbol": "CL=F",
                "enabled": True,
            },
            {
                "symbol": "XAG/USD",
                "assetClass": "COMMODITY",
                "provider": "YFINANCE",
                "providerSymbol": "SI=F",
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
                UPDATE symbol_provider_mappings
                SET provider_symbol = 'BTC/USD_TEST'
                WHERE supported_symbol_id = (
                    SELECT id FROM supported_symbols WHERE symbol = 'BTC/USD'
                )
                  AND is_active
                """
            )
        )

    class FakeProvider:
        def __init__(self) -> None:
            self.requested_provider_symbols: list[str] = []

        async def fetch_latest_prices(
            self,
            symbols: list[SupportedSymbol],
        ) -> ProviderQuoteBatch:
            self.requested_provider_symbols.extend(symbol.provider_symbol for symbol in symbols)
            return ProviderQuoteBatch(
                prices={"BTC/USD_TEST": Decimal("123.4500")},
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
    assert provider.requested_provider_symbols == ["BTC/USD_TEST"]
    quote = response.json()["quotes"][0]
    assert set(quote) == {"symbol", "price", "receivedAt"}
    assert quote["symbol"] == "BTC/USD"
    assert quote["price"] == "123.45"
    assert quote["receivedAt"].endswith("Z")


async def test_quotes_accept_non_default_provider_and_keep_partial_outcomes(
    database_engine: AsyncEngine,
) -> None:
    class FakeProvider:
        def __init__(self) -> None:
            self.requested: list[SupportedSymbol] = []

        async def fetch_latest_prices(
            self,
            symbols: list[SupportedSymbol],
        ) -> ProviderQuoteBatch:
            self.requested.extend(symbols)
            return ProviderQuoteBatch(
                prices={symbol.provider_symbol: Decimal("321.45") for symbol in symbols},
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
                params={"symbols": "AAPL,XAU/USD", "provider": "YFINANCE"},
            )
    finally:
        app.dependency_overrides.clear()
        get_quote_cache.cache_clear()

    assert response.status_code == 200
    assert [symbol.provider for symbol in provider.requested] == ["YFINANCE"]
    assert response.json()["quotes"][0]["symbol"] == "AAPL"
    assert response.json()["errors"] == [
        {
            "symbol": "XAU/USD",
            "code": "UNSUPPORTED_PROVIDER",
            "message": "The requested provider is not supported for this symbol.",
        }
    ]
