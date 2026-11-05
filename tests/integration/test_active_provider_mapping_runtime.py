from asyncio import to_thread
from datetime import UTC, datetime, timedelta

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from alembic import command
from app.db.repositories import PostgresCandleRepository, PostgresSymbolRepository
from app.domain.errors import DatabaseUnavailableError

pytestmark = pytest.mark.integration

# Exercise the historical registry and its migrations at their original boundary.
MIGRATION_TARGET = "20260727_0020"


async def _switch_btc_to_yfinance(database_engine: AsyncEngine) -> None:
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE symbol_provider_mappings
                SET is_active = false
                WHERE supported_symbol_id = (
                    SELECT id FROM supported_symbols WHERE symbol = 'BTC/USD'
                )
                """
            )
        )
        await connection.execute(
            text(
                """
                UPDATE symbol_provider_mappings
                SET is_active = true
                WHERE supported_symbol_id = (
                    SELECT id FROM supported_symbols WHERE symbol = 'BTC/USD'
                )
                  AND provider = 'YFINANCE'
                  AND provider_symbol = 'BTC-USD'
                """
            )
        )


async def _activate_btc_twelvedata(database_engine: AsyncEngine) -> None:
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE symbol_provider_mappings
                SET is_active = true
                WHERE supported_symbol_id = (
                    SELECT id FROM supported_symbols WHERE symbol = 'BTC/USD'
                )
                  AND provider = 'TWELVE_DATA'
                  AND provider_symbol = 'BTC/USD'
                """
            )
        )


async def test_symbol_repositories_resolve_the_active_mapping(
    database_engine: AsyncEngine,
) -> None:
    await _switch_btc_to_yfinance(database_engine)
    session_factory = async_sessionmaker(database_engine, expire_on_commit=False)

    async with session_factory() as session:
        symbols = await PostgresSymbolRepository(session).list_enabled()
    listed = next(symbol for symbol in symbols if symbol.symbol == "BTC/USD")
    resolved = await PostgresCandleRepository(session_factory).get_enabled_symbol("BTC/USD")

    assert (listed.provider, listed.provider_symbol) == ("YFINANCE", "BTC-USD")
    assert resolved is not None
    assert (resolved.provider, resolved.provider_symbol) == ("YFINANCE", "BTC-USD")


async def test_symbol_repositories_fail_closed_without_an_active_mapping(
    database_engine: AsyncEngine,
) -> None:
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE symbol_provider_mappings
                SET is_active = false
                WHERE supported_symbol_id = (
                    SELECT id FROM supported_symbols WHERE symbol = 'BTC/USD'
                )
                """
            )
        )
    session_factory = async_sessionmaker(database_engine, expire_on_commit=False)

    async with session_factory() as session:
        with pytest.raises(DatabaseUnavailableError):
            await PostgresSymbolRepository(session).list_enabled()
    with pytest.raises(DatabaseUnavailableError):
        await PostgresCandleRepository(session_factory).get_enabled_symbol("BTC/USD")
    await _activate_btc_twelvedata(database_engine)


async def test_provider_switch_keeps_old_candles_under_their_recorded_identity(
    database_engine: AsyncEngine,
) -> None:
    open_time = datetime(2026, 7, 27, tzinfo=UTC)
    async with database_engine.begin() as connection:
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
                    'BTC/USD',
                    'CRYPTO',
                    'TWELVE_DATA',
                    'BTC/USD',
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
    await _switch_btc_to_yfinance(database_engine)
    session_factory = async_sessionmaker(database_engine, expire_on_commit=False)
    repository = PostgresCandleRepository(session_factory)
    symbol = await repository.get_enabled_symbol("BTC/USD")

    assert symbol is not None
    assert (
        await repository.list_complete(
            symbol,
            "1m",
            open_time,
            open_time + timedelta(minutes=2),
        )
        == []
    )
    async with database_engine.connect() as connection:
        old_candle = (
            await connection.execute(
                text(
                    """
                    SELECT provider, provider_symbol
                    FROM market_data_candles
                    WHERE symbol = 'BTC/USD' AND open_time = :open_time
                    """
                ),
                {"open_time": open_time},
            )
        ).one()
    assert old_candle == ("TWELVE_DATA", "BTC/USD")


async def test_head_schema_contains_only_normalized_provider_storage(
    database_engine: AsyncEngine,
) -> None:
    async with database_engine.connect() as connection:
        schema = await connection.run_sync(
            lambda sync_connection: {
                "columns": {
                    column["name"]
                    for column in inspect(sync_connection).get_columns("supported_symbols")
                },
                "constraints": {
                    constraint["name"]
                    for constraint in inspect(sync_connection).get_unique_constraints(
                        "supported_symbols"
                    )
                },
            }
        )
        mapping_count = (
            await connection.execute(text("SELECT count(*) FROM symbol_provider_mappings"))
        ).scalar_one()

    assert {"provider", "provider_symbol"}.isdisjoint(schema["columns"])
    assert "uq_supported_symbols_provider_symbol" not in schema["constraints"]
    assert mapping_count == 29


async def test_contract_downgrade_reconstructs_current_active_mapping(
    database_engine: AsyncEngine,
) -> None:
    await _switch_btc_to_yfinance(database_engine)
    config = Config("alembic.ini")
    await to_thread(command.downgrade, config, "20260727_0019")

    async with database_engine.connect() as connection:
        legacy = (
            await connection.execute(
                text(
                    """
                    SELECT provider, provider_symbol
                    FROM supported_symbols
                    WHERE symbol = 'BTC/USD'
                    """
                )
            )
        ).one()

    assert legacy == ("YFINANCE", "BTC-USD")
    await to_thread(command.upgrade, config, MIGRATION_TARGET)


async def test_contract_upgrade_aborts_before_drop_when_mapping_is_missing(
    database_engine: AsyncEngine,
) -> None:
    config = Config("alembic.ini")
    await to_thread(command.downgrade, config, "20260727_0019")
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE symbol_provider_mappings
                SET is_active = false
                WHERE supported_symbol_id = (
                    SELECT id FROM supported_symbols WHERE symbol = 'BTC/USD'
                )
                """
            )
        )

    with pytest.raises(RuntimeError, match="exactly one active provider mapping"):
        await to_thread(command.upgrade, config, MIGRATION_TARGET)

    async with database_engine.connect() as connection:
        columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"]
                for column in inspect(sync_connection).get_columns("supported_symbols")
            }
        )
    assert {"provider", "provider_symbol"} <= columns

    await _activate_btc_twelvedata(database_engine)
    await to_thread(command.upgrade, config, MIGRATION_TARGET)
