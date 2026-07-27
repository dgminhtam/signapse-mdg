from asyncio import to_thread
from datetime import UTC, datetime, timedelta

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import command

pytestmark = pytest.mark.integration

INSERT_MAPPING = text(
    """
    INSERT INTO symbol_provider_mappings (
        supported_symbol_id,
        provider,
        provider_symbol,
        is_active
    )
    VALUES (
        :supported_symbol_id,
        :provider,
        :provider_symbol,
        :is_active
    )
    """
)


async def test_mapping_schema_matches_active_selection_design(
    database_engine: AsyncEngine,
) -> None:
    async with database_engine.connect() as connection:
        schema = await connection.run_sync(
            lambda sync_connection: {
                "columns": {
                    column["name"]
                    for column in inspect(sync_connection).get_columns("symbol_provider_mappings")
                },
                "unique_constraints": {
                    tuple(constraint["column_names"])
                    for constraint in inspect(sync_connection).get_unique_constraints(
                        "symbol_provider_mappings"
                    )
                },
                "indexes": {
                    index["name"]: index
                    for index in inspect(sync_connection).get_indexes("symbol_provider_mappings")
                },
                "check_constraints": {
                    constraint["name"]
                    for constraint in inspect(sync_connection).get_check_constraints(
                        "symbol_provider_mappings"
                    )
                },
                "foreign_keys": inspect(sync_connection).get_foreign_keys(
                    "symbol_provider_mappings"
                ),
                "legacy_columns": {
                    column["name"]
                    for column in inspect(sync_connection).get_columns("supported_symbols")
                },
                "candle_columns": {
                    column["name"]
                    for column in inspect(sync_connection).get_columns("market_data_candles")
                },
            }
        )

    assert schema["columns"] == {
        "id",
        "supported_symbol_id",
        "provider",
        "provider_symbol",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert schema["unique_constraints"] == {
        ("supported_symbol_id", "provider"),
        ("provider", "provider_symbol"),
    }
    active_index = schema["indexes"]["ux_symbol_provider_mappings_active_symbol"]
    assert active_index["column_names"] == ["supported_symbol_id"]
    assert active_index["unique"] is True
    assert schema["check_constraints"] == {
        "ck_symbol_provider_mappings_provider_nonempty",
        "ck_symbol_provider_mappings_provider_symbol_nonempty",
    }
    assert schema["foreign_keys"][0]["constrained_columns"] == ["supported_symbol_id"]
    assert schema["foreign_keys"][0]["referred_table"] == "supported_symbols"
    assert schema["foreign_keys"][0]["options"] == {"ondelete": "CASCADE"}
    assert {"provider", "provider_symbol"}.isdisjoint(schema["legacy_columns"])
    assert "provider_mapping_id" not in schema["candle_columns"]


async def test_fresh_upgrade_preserves_every_legacy_mapping_as_active(
    database_engine: AsyncEngine,
) -> None:
    config = Config("alembic.ini")
    await to_thread(command.downgrade, config, "20260727_0016")
    async with database_engine.begin() as connection:
        await connection.execute(
            text("UPDATE supported_symbols SET enabled = false WHERE symbol = 'USD/JPY'")
        )
        legacy_rows = (
            await connection.execute(
                text(
                    """
                    SELECT id, provider, provider_symbol, enabled, created_at, updated_at
                    FROM supported_symbols
                    ORDER BY id
                    """
                )
            )
        ).all()

    await to_thread(command.upgrade, config, "20260727_0018")
    async with database_engine.connect() as connection:
        mapping_rows = (
            await connection.execute(
                text(
                    """
                    SELECT
                        supported_symbol_id,
                        provider,
                        provider_symbol,
                        is_active,
                        created_at,
                        updated_at
                    FROM symbol_provider_mappings
                    ORDER BY supported_symbol_id
                    """
                )
            )
        ).all()

    assert len(mapping_rows) == len(legacy_rows)
    for legacy, mapping in zip(legacy_rows, mapping_rows, strict=True):
        assert mapping.supported_symbol_id == legacy.id
        assert mapping.provider == legacy.provider
        assert mapping.provider_symbol == legacy.provider_symbol
        assert mapping.is_active is True
        assert mapping.created_at == legacy.created_at
        assert mapping.updated_at == legacy.updated_at

    assert any(not row.enabled for row in legacy_rows)


async def test_multiple_mappings_and_active_selection_constraints(
    database_engine: AsyncEngine,
) -> None:
    async with database_engine.begin() as connection:
        symbol_ids = []
        for suffix in ("A", "B"):
            symbol_ids.append(
                (
                    await connection.execute(
                        text(
                            """
                            INSERT INTO supported_symbols (
                                symbol,
                                asset_class,
                                price_display_decimals
                            )
                            VALUES (:symbol, 'TEST', 2)
                            RETURNING id
                            """
                        ),
                        {
                            "symbol": f"TEST/{suffix}",
                        },
                    )
                ).scalar_one()
            )

        for symbol_id, provider in zip(symbol_ids, ("PROVIDER_A", "PROVIDER_B"), strict=True):
            await connection.execute(
                INSERT_MAPPING,
                {
                    "supported_symbol_id": symbol_id,
                    "provider": provider,
                    "provider_symbol": f"SYMBOL_{provider[-1]}",
                    "is_active": True,
                },
            )

        await connection.execute(
            INSERT_MAPPING,
            {
                "supported_symbol_id": symbol_ids[0],
                "provider": "PROVIDER_ALT",
                "provider_symbol": "SYMBOL_ALT",
                "is_active": False,
            },
        )

        invalid_rows = [
            (symbol_ids[1], "PROVIDER_A", "SYMBOL_A", False),
            (symbol_ids[0], "PROVIDER_A", "OTHER", False),
            (symbol_ids[0], "PROVIDER_NEW", "SYMBOL_NEW", True),
            (symbol_ids[0], " ", "BLANK_PROVIDER", False),
            (symbol_ids[0], "BLANK_SYMBOL", " ", False),
        ]
        for symbol_id, provider, provider_symbol, is_active in invalid_rows:
            savepoint = await connection.begin_nested()
            with pytest.raises(IntegrityError):
                await connection.execute(
                    INSERT_MAPPING,
                    {
                        "supported_symbol_id": symbol_id,
                        "provider": provider,
                        "provider_symbol": provider_symbol,
                        "is_active": is_active,
                    },
                )
            await savepoint.rollback()

        mappings = (
            await connection.execute(
                text(
                    """
                    SELECT provider, is_active
                    FROM symbol_provider_mappings
                    WHERE supported_symbol_id = :id
                    ORDER BY provider
                    """
                ),
                {"id": symbol_ids[0]},
            )
        ).all()

    assert mappings == [
        ("PROVIDER_A", True),
        ("PROVIDER_ALT", False),
    ]


async def test_mapping_rows_cascade_with_supported_symbol(
    database_engine: AsyncEngine,
) -> None:
    async with database_engine.begin() as connection:
        supported_symbol_id = (
            await connection.execute(
                text(
                    """
                    INSERT INTO supported_symbols (
                        symbol,
                        asset_class,
                        price_display_decimals
                    )
                    VALUES ('CASCADE/TEST', 'TEST', 2)
                    RETURNING id
                    """
                )
            )
        ).scalar_one()
        await connection.execute(
            INSERT_MAPPING,
            {
                "supported_symbol_id": supported_symbol_id,
                "provider": "CASCADE",
                "provider_symbol": "CASCADE_TEST",
                "is_active": True,
            },
        )
        await connection.execute(
            text("DELETE FROM supported_symbols WHERE id = :id"),
            {"id": supported_symbol_id},
        )
        mapping_count = (
            await connection.execute(
                text(
                    """
                    SELECT count(*)
                    FROM symbol_provider_mappings
                    WHERE supported_symbol_id = :id
                    """
                ),
                {"id": supported_symbol_id},
            )
        ).scalar_one()

    assert mapping_count == 0


async def test_incremental_upgrade_and_downgrade_preserve_rows(
    database_engine: AsyncEngine,
) -> None:
    start = datetime(2026, 7, 27, tzinfo=UTC)
    async with database_engine.begin() as connection:
        supported_symbol_id = (
            await connection.execute(
                text(
                    """
                    INSERT INTO supported_symbols (
                        symbol,
                        asset_class,
                        price_display_decimals
                    )
                    VALUES ('PRESERVE/TEST', 'TEST', 2)
                    RETURNING id
                    """
                )
            )
        ).scalar_one()
        for provider, provider_symbol, is_active in (
            ("PRIMARY", "PRIMARY_TEST", True),
            ("SECONDARY", "SECONDARY_TEST", False),
        ):
            await connection.execute(
                INSERT_MAPPING,
                {
                    "supported_symbol_id": supported_symbol_id,
                    "provider": provider,
                    "provider_symbol": provider_symbol,
                    "is_active": is_active,
                },
            )
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
                    'PRESERVE/TEST',
                    'TEST',
                    'PRIMARY',
                    'PRIMARY_TEST',
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
            {"open_time": start, "close_time": start + timedelta(minutes=1)},
        )
        mappings_before = (
            await connection.execute(
                text(
                    """
                    SELECT id, provider, provider_symbol, is_active, created_at, updated_at
                    FROM symbol_provider_mappings
                    WHERE supported_symbol_id = :id
                    ORDER BY id
                    """
                ),
                {"id": supported_symbol_id},
            )
        ).all()

    config = Config("alembic.ini")
    await to_thread(command.downgrade, config, "20260727_0017")
    async with database_engine.connect() as connection:
        downgraded_rows = (
            await connection.execute(
                text(
                    """
                    SELECT id, provider, provider_symbol, quote_priority,
                           candle_priority, stream_priority
                    FROM symbol_provider_mappings
                    WHERE supported_symbol_id = :id
                    ORDER BY id
                    """
                ),
                {"id": supported_symbol_id},
            )
        ).all()
        candle_count = (
            await connection.execute(
                text(
                    """
                    SELECT count(*)
                    FROM market_data_candles
                    WHERE symbol = 'PRESERVE/TEST'
                    """
                )
            )
        ).scalar_one()

    assert [(row.provider, row.provider_symbol) for row in downgraded_rows] == [
        ("PRIMARY", "PRIMARY_TEST"),
        ("SECONDARY", "SECONDARY_TEST"),
    ]
    assert [
        (row.quote_priority, row.candle_priority, row.stream_priority) for row in downgraded_rows
    ] == [(0, 0, 0), (1, 1, 1)]
    assert candle_count == 1

    await to_thread(command.upgrade, config, "head")
    async with database_engine.connect() as connection:
        mappings_after = (
            await connection.execute(
                text(
                    """
                    SELECT id, provider, provider_symbol, is_active, created_at, updated_at
                    FROM symbol_provider_mappings
                    WHERE supported_symbol_id = :id
                    ORDER BY id
                    """
                ),
                {"id": supported_symbol_id},
            )
        ).all()
        preserved_counts = (
            await connection.execute(
                text(
                    """
                    SELECT
                        (SELECT count(*) FROM supported_symbols WHERE id = :id),
                        (
                            SELECT count(*)
                            FROM market_data_candles
                            WHERE symbol = 'PRESERVE/TEST'
                        )
                    """
                ),
                {"id": supported_symbol_id},
            )
        ).one()

    assert mappings_after == mappings_before
    assert preserved_counts == (1, 1)


async def test_full_downgrade_drops_only_mapping_table(
    database_engine: AsyncEngine,
) -> None:
    config = Config("alembic.ini")
    await to_thread(command.downgrade, config, "20260727_0018")
    async with database_engine.connect() as connection:
        legacy_rows_before = (
            await connection.execute(
                text(
                    """
                    SELECT id, provider, provider_symbol
                    FROM supported_symbols
                    ORDER BY id
                    """
                )
            )
        ).all()

    await to_thread(command.downgrade, config, "20260727_0016")
    async with database_engine.connect() as connection:
        state = await connection.run_sync(
            lambda sync_connection: {
                "tables": set(inspect(sync_connection).get_table_names()),
                "legacy_columns": {
                    column["name"]
                    for column in inspect(sync_connection).get_columns("supported_symbols")
                },
            }
        )
        legacy_rows_after = (
            await connection.execute(
                text(
                    """
                    SELECT id, provider, provider_symbol
                    FROM supported_symbols
                    ORDER BY id
                    """
                )
            )
        ).all()

    assert "symbol_provider_mappings" not in state["tables"]
    assert {"provider", "provider_symbol"} <= state["legacy_columns"]
    assert legacy_rows_after == legacy_rows_before
