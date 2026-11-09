import importlib.util
from asyncio import to_thread
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import command

pytestmark = pytest.mark.integration

# Exercise the historical registry and its migrations at their original boundary.
MIGRATION_TARGET = "20260727_0020"

EXPECTED_DEFAULTS = {
    "AAPL": ("TWELVE_DATA", "AAPL"),
    "AUD/USD": ("YFINANCE", "AUDUSD=X"),
    "BRENT": ("YFINANCE", "BZ=F"),
    "BTC/USD": ("TWELVE_DATA", "BTC/USD"),
    "COFFEE": ("YFINANCE", "KC=F"),
    "CORN": ("YFINANCE", "ZC=F"),
    "DJI": ("YFINANCE", "^DJI"),
    "ETH/USD": ("BINANCE_SPOT", "ETHUSD"),
    "EUR/USD": ("TWELVE_DATA", "EUR/USD"),
    "GBP/USD": ("YFINANCE", "GBPUSD=X"),
    "MSFT": ("YFINANCE", "MSFT"),
    "NATGAS": ("YFINANCE", "NG=F"),
    "NDX": ("YFINANCE", "^NDX"),
    "NVDA": ("YFINANCE", "NVDA"),
    "QQQ": ("TWELVE_DATA", "QQQ"),
    "SPX": ("YFINANCE", "^GSPC"),
    "SPY": ("YFINANCE", "SPY"),
    "SUGAR": ("YFINANCE", "SB=F"),
    "TSLA": ("YFINANCE", "TSLA"),
    "USD/JPY": ("YFINANCE", "JPY=X"),
    "WHEAT": ("YFINANCE", "ZW=F"),
    "WTI": ("YFINANCE", "CL=F"),
    "XAG/USD": ("YFINANCE", "SI=F"),
    "XAU/USD": ("TWELVE_DATA", "XAU/USD"),
}

EXPECTED_ALTERNATIVES = {
    "AAPL": ("YFINANCE", "AAPL"),
    "BTC/USD": ("YFINANCE", "BTC-USD"),
    "ETH/USD": ("YFINANCE", "ETH-USD"),
    "EUR/USD": ("YFINANCE", "EURUSD=X"),
    "QQQ": ("YFINANCE", "QQQ"),
}


def load_seed_migration() -> ModuleType:
    migration_path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20260727_0019_seed_24_asset_provider_mappings.py"
    )
    spec = importlib.util.spec_from_file_location("seed_24_asset_provider_mappings", migration_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load provider mapping seed migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def fetch_mapping_state(
    database_engine: AsyncEngine,
) -> list[object]:
    async with database_engine.connect() as connection:
        mappings = (
            await connection.execute(
                text(
                    """
                    SELECT
                        supported_symbols.symbol,
                        symbol_provider_mappings.provider,
                        symbol_provider_mappings.provider_symbol,
                        symbol_provider_mappings.is_active
                    FROM symbol_provider_mappings
                    JOIN supported_symbols
                      ON supported_symbols.id =
                         symbol_provider_mappings.supported_symbol_id
                    WHERE supported_symbols.symbol = ANY(:symbols)
                    ORDER BY
                        supported_symbols.symbol,
                        symbol_provider_mappings.is_active DESC,
                        symbol_provider_mappings.provider
                    """
                ),
                {"symbols": list(EXPECTED_DEFAULTS)},
            )
        ).all()
    return mappings


async def test_fresh_upgrade_seeds_approved_24_asset_matrix(
    database_engine: AsyncEngine,
) -> None:
    mappings = await fetch_mapping_state(database_engine)
    active = {row.symbol: (row.provider, row.provider_symbol) for row in mappings if row.is_active}
    inactive = {
        row.symbol: (row.provider, row.provider_symbol) for row in mappings if not row.is_active
    }

    assert len(mappings) == 29
    assert active == EXPECTED_DEFAULTS
    assert inactive == EXPECTED_ALTERNATIVES
    assert [(row.provider, row.provider_symbol) for row in mappings if row.symbol == "XAU/USD"] == [
        ("TWELVE_DATA", "XAU/USD")
    ]
    assert all(row.provider_symbol not in {"GC=F", "XAUUSD=X"} for row in mappings)


async def test_seed_is_repeatable_and_preserves_disabled_asset_and_custom_mapping(
    database_engine: AsyncEngine,
) -> None:
    config = Config("alembic.ini")
    await to_thread(command.downgrade, config, "20260727_0018")
    async with database_engine.begin() as connection:
        await connection.execute(
            text("UPDATE supported_symbols SET enabled = false WHERE symbol = 'USD/JPY'")
        )
        custom_before = (
            await connection.execute(
                text(
                    """
                    INSERT INTO symbol_provider_mappings (
                        supported_symbol_id,
                        provider,
                        provider_symbol,
                        is_active
                    )
                    SELECT id, 'CUSTOM', 'AAPL_CUSTOM', false
                    FROM supported_symbols
                    WHERE symbol = 'AAPL'
                    RETURNING id, created_at, updated_at
                    """
                )
            )
        ).one()

    await to_thread(command.upgrade, config, "20260727_0019")
    migration = load_seed_migration()
    async with database_engine.begin() as connection:
        await connection.run_sync(migration.seed_provider_mappings)
        await connection.run_sync(migration.seed_provider_mappings)
        custom_after = (
            await connection.execute(
                text(
                    """
                    SELECT id, created_at, updated_at, is_active
                    FROM symbol_provider_mappings
                    WHERE provider = 'CUSTOM' AND provider_symbol = 'AAPL_CUSTOM'
                    """
                )
            )
        ).one()
        disabled = (
            await connection.execute(
                text(
                    """
                    SELECT
                        supported_symbols.enabled,
                        symbol_provider_mappings.provider,
                        symbol_provider_mappings.provider_symbol,
                        symbol_provider_mappings.is_active
                    FROM supported_symbols
                    JOIN symbol_provider_mappings
                      ON symbol_provider_mappings.supported_symbol_id = supported_symbols.id
                     AND symbol_provider_mappings.is_active
                    WHERE supported_symbols.symbol = 'USD/JPY'
                    """
                )
            )
        ).one()

    mappings = await fetch_mapping_state(database_engine)
    assert len(mappings) == 30
    assert custom_after == (*custom_before, False)
    assert disabled == (False, "YFINANCE", "JPY=X", True)
    await to_thread(command.upgrade, config, MIGRATION_TARGET)


async def test_seed_fails_on_provider_identity_owned_by_another_asset(
    database_engine: AsyncEngine,
) -> None:
    config = Config("alembic.ini")
    await to_thread(command.downgrade, config, "20260727_0018")
    async with database_engine.begin() as connection:
        conflict_id = (
            await connection.execute(
                text(
                    """
                    INSERT INTO supported_symbols (
                        symbol,
                        asset_class,
                        provider,
                        provider_symbol,
                        price_display_decimals
                    )
                    VALUES ('CONFLICT/AAPL', 'TEST', 'CUSTOM', 'CONFLICT_AAPL', 2)
                    RETURNING id
                    """
                )
            )
        ).scalar_one()
        await connection.execute(
            text(
                """
                INSERT INTO symbol_provider_mappings (
                    supported_symbol_id,
                    provider,
                    provider_symbol,
                    is_active
                )
                VALUES (:id, 'YFINANCE', 'AAPL', true)
                """
            ),
            {"id": conflict_id},
        )

    with pytest.raises(IntegrityError):
        await to_thread(command.upgrade, config, MIGRATION_TARGET)

    async with database_engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM supported_symbols WHERE symbol = 'CONFLICT/AAPL'")
        )
    await to_thread(command.upgrade, config, MIGRATION_TARGET)


async def test_downgrade_restores_0018_defaults_and_preserves_custom_and_candles(
    database_engine: AsyncEngine,
) -> None:
    open_time = datetime(2026, 7, 27, tzinfo=UTC)
    async with database_engine.begin() as connection:
        custom_before = (
            await connection.execute(
                text(
                    """
                    INSERT INTO symbol_provider_mappings (
                        supported_symbol_id,
                        provider,
                        provider_symbol,
                        is_active
                    )
                    SELECT id, 'CUSTOM', 'AUD_CUSTOM', false
                    FROM supported_symbols
                    WHERE symbol = 'AUD/USD'
                    RETURNING id, created_at, updated_at
                    """
                )
            )
        ).one()
        await connection.execute(
            text(
                """
                INSERT INTO market_data_candles (
                    symbol,
                    asset_class,
                    provider,
                    provider_symbol,
                    timeframe,
                    open_time,
                    close_time,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    complete
                )
                VALUES (
                    'AUD/USD',
                    'FOREX',
                    'YFINANCE',
                    'AUDUSD=X',
                    '1m',
                    :open_time,
                    :close_time,
                    1,
                    1,
                    1,
                    1,
                    0,
                    true
                )
                """
            ),
            {"open_time": open_time, "close_time": open_time + timedelta(minutes=1)},
        )

    config = Config("alembic.ini")
    await to_thread(command.downgrade, config, "20260727_0018")
    async with database_engine.connect() as connection:
        custom_after = (
            await connection.execute(
                text(
                    """
                    SELECT id, created_at, updated_at, is_active
                    FROM symbol_provider_mappings
                    WHERE provider = 'CUSTOM' AND provider_symbol = 'AUD_CUSTOM'
                    """
                )
            )
        ).one()
        restored = (
            await connection.execute(
                text(
                    """
                    SELECT
                        supported_symbols.provider,
                        supported_symbols.provider_symbol,
                        symbol_provider_mappings.is_active
                    FROM supported_symbols
                    JOIN symbol_provider_mappings
                      ON symbol_provider_mappings.supported_symbol_id = supported_symbols.id
                     AND symbol_provider_mappings.provider = 'TWELVE_DATA'
                     AND symbol_provider_mappings.provider_symbol = 'AUD/USD'
                    WHERE supported_symbols.symbol = 'AUD/USD'
                    """
                )
            )
        ).one()
        candle = (
            await connection.execute(
                text(
                    """
                    SELECT provider, provider_symbol, open_time
                    FROM market_data_candles
                    WHERE symbol = 'AUD/USD' AND open_time = :open_time
                    """
                ),
                {"open_time": open_time},
            )
        ).one()

    assert custom_after == (*custom_before, False)
    assert restored == ("TWELVE_DATA", "AUD/USD", True)
    assert candle == ("YFINANCE", "AUDUSD=X", open_time)
    await to_thread(command.upgrade, config, MIGRATION_TARGET)
