from datetime import UTC, datetime

import pytest
from sqlalchemy import DateTime, Text, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.models import EconomicCalendarEventModel

pytestmark = pytest.mark.integration


async def test_economic_calendar_migration_has_expected_schema(
    database_engine: AsyncEngine,
) -> None:
    async with database_engine.connect() as connection:
        table_names = await connection.run_sync(
            lambda sync_connection: set(inspect(sync_connection).get_table_names())
        )
        columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"]: column
                for column in inspect(sync_connection).get_columns("economic_calendar_events")
            }
        )
        unique_constraints = await connection.run_sync(
            lambda sync_connection: {
                constraint["name"]: tuple(constraint["column_names"])
                for constraint in inspect(sync_connection).get_unique_constraints(
                    "economic_calendar_events"
                )
            }
        )
        check_constraints = await connection.run_sync(
            lambda sync_connection: {
                constraint["name"]: constraint["sqltext"]
                for constraint in inspect(sync_connection).get_check_constraints(
                    "economic_calendar_events"
                )
            }
        )
        indexes = await connection.run_sync(
            lambda sync_connection: {
                index["name"]: tuple(index["column_names"])
                for index in inspect(sync_connection).get_indexes("economic_calendar_events")
            }
        )

    assert "economic_calendar_events" in table_names
    assert set(columns) == {
        "id",
        "calendar_type",
        "external_event_id",
        "name",
        "currency",
        "impact",
        "scheduled_at",
        "actual",
        "forecast",
        "previous",
        "revision",
        "actual_better_worse",
        "revision_better_worse",
        "description",
        "news_url",
        "enrichment_attempted_at",
        "first_seen_at",
        "last_seen_at",
        "last_changed_at",
        "created_at",
        "updated_at",
    }
    for name in (
        "actual",
        "forecast",
        "previous",
        "revision",
        "actual_better_worse",
        "revision_better_worse",
        "description",
        "news_url",
    ):
        assert isinstance(columns[name]["type"], Text)
        assert columns[name]["nullable"] is True
    assert isinstance(columns["enrichment_attempted_at"]["type"], DateTime)
    assert columns["enrichment_attempted_at"]["type"].timezone is True
    assert columns["enrichment_attempted_at"]["nullable"] is True
    for name in (
        "scheduled_at",
        "first_seen_at",
        "last_seen_at",
        "last_changed_at",
        "created_at",
        "updated_at",
    ):
        assert isinstance(columns[name]["type"], DateTime)
        assert columns[name]["type"].timezone is True
        assert columns[name]["nullable"] is False
    assert unique_constraints["uq_economic_calendar_events_identity"] == (
        "calendar_type",
        "external_event_id",
    )
    assert "ck_economic_calendar_events_calendar_type" in check_constraints
    assert indexes["ix_economic_calendar_events_scheduled_at"] == ("scheduled_at",)
    assert indexes["ix_economic_calendar_events_type_scheduled_at"] == (
        "calendar_type",
        "scheduled_at",
    )
    assert indexes["ix_economic_calendar_events_currency_scheduled_at"] == (
        "currency",
        "scheduled_at",
    )


def test_economic_calendar_model_matches_table_contract() -> None:
    table = EconomicCalendarEventModel.__table__

    assert table.name == "economic_calendar_events"
    assert set(table.c.keys()) == {
        "id",
        "calendar_type",
        "external_event_id",
        "name",
        "currency",
        "impact",
        "scheduled_at",
        "actual",
        "forecast",
        "previous",
        "revision",
        "actual_better_worse",
        "revision_better_worse",
        "description",
        "news_url",
        "enrichment_attempted_at",
        "first_seen_at",
        "last_seen_at",
        "last_changed_at",
        "created_at",
        "updated_at",
    }
    assert {
        constraint.name
        for constraint in table.constraints
    } >= {
        "uq_economic_calendar_events_identity",
        "ck_economic_calendar_events_calendar_type",
    }
    assert {
        index.name: tuple(column.name for column in index.columns)
        for index in table.indexes
    } == {
        "ix_economic_calendar_events_scheduled_at": ("scheduled_at",),
        "ix_economic_calendar_events_type_scheduled_at": (
            "calendar_type",
            "scheduled_at",
        ),
        "ix_economic_calendar_events_currency_scheduled_at": (
            "currency",
            "scheduled_at",
        ),
    }


async def test_economic_calendar_identity_and_type_constraints(
    database_engine: AsyncEngine,
) -> None:
    scheduled_at = datetime(2026, 7, 1, 12, 30, tzinfo=UTC)
    async with database_engine.begin() as connection:
        await _insert_event(connection, "FOREX", "123", scheduled_at)
        await _insert_event(connection, "METALS", "123", scheduled_at)

    with pytest.raises(IntegrityError):
        async with database_engine.begin() as connection:
            await _insert_event(connection, "FOREX", "123", scheduled_at)

    with pytest.raises(IntegrityError):
        async with database_engine.begin() as connection:
            await _insert_event(connection, "UNKNOWN", "999", scheduled_at)


async def _insert_event(
    connection: object,
    calendar_type: str,
    external_event_id: str,
    scheduled_at: datetime,
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO economic_calendar_events (
                calendar_type,
                external_event_id,
                name,
                currency,
                impact,
                scheduled_at
            )
            VALUES (
                :calendar_type,
                :external_event_id,
                'Non-Farm Employment Change',
                'USD',
                'HIGH',
                :scheduled_at
            )
            """
        ),
        {
            "calendar_type": calendar_type,
            "external_event_id": external_event_id,
            "scheduled_at": scheduled_at,
        },
    )
