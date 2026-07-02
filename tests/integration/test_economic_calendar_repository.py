from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.db.repositories import PostgresEconomicCalendarRepository
from app.domain.economic_calendar import EconomicCalendarFetchedEvent
from app.services.economic_calendar import parse_economic_calendar_request

pytestmark = pytest.mark.integration


async def test_economic_calendar_repository_filters_orders_and_limits(
    database_engine: AsyncEngine,
) -> None:
    async with database_engine.begin() as connection:
        await _insert_event(
            connection,
            "FOREX",
            "2",
            "USD",
            "HIGH",
            datetime(2026, 7, 2, tzinfo=UTC),
        )
        await _insert_event(
            connection,
            "METALS",
            "1",
            "XAU",
            "HIGH",
            datetime(2026, 7, 1, tzinfo=UTC),
        )
        await _insert_event(
            connection,
            "FOREX",
            "1",
            "EUR",
            "LOW",
            datetime(2026, 7, 1, tzinfo=UTC),
        )
        await _insert_event(
            connection,
            "CRYPTO",
            "9",
            "BTC",
            "HIGH",
            datetime(2026, 7, 9, tzinfo=UTC),
        )

    repository = PostgresEconomicCalendarRepository(async_sessionmaker(database_engine))
    request = parse_economic_calendar_request(
        "2026-07-01T00:00:00Z",
        "2026-07-08T00:00:00Z",
        raw_types="FOREX,METALS",
        raw_impact="HIGH",
        raw_limit="2",
    )

    events = await repository.list_events(request)

    assert [(event.calendar_type, event.external_event_id) for event in events] == [
        ("METALS", "1"),
        ("FOREX", "2"),
    ]


async def test_economic_calendar_repository_upsert_preserves_lifecycle_timestamps(
    database_engine: AsyncEngine,
) -> None:
    repository = PostgresEconomicCalendarRepository(async_sessionmaker(database_engine))
    event = EconomicCalendarFetchedEvent(
        calendar_type="FOREX",
        external_event_id="123",
        name="Event",
        currency="USD",
        impact="high",
        scheduled_at=datetime(2026, 7, 1, 12, tzinfo=UTC),
        actual=None,
        forecast="100K",
        previous="90K",
        revision=None,
        actual_better_worse=None,
        revision_better_worse=None,
    )

    await repository.upsert_events([event])
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE economic_calendar_events
                SET last_seen_at = '2026-01-01T00:00:00Z',
                    last_changed_at = '2026-01-02T00:00:00Z'
                WHERE calendar_type = 'FOREX' AND external_event_id = '123'
                """
            )
        )

    await repository.upsert_events([event])
    unchanged = await _get_lifecycle(database_engine)

    await repository.upsert_events([replace(event, actual="110K")])
    changed = await _get_lifecycle(database_engine)

    assert unchanged["first_seen_at"] == changed["first_seen_at"]
    assert unchanged["last_seen_at"] > datetime(2026, 1, 1, tzinfo=UTC)
    assert unchanged["last_changed_at"] == datetime(2026, 1, 2, tzinfo=UTC)
    assert changed["last_changed_at"] > unchanged["last_changed_at"]


async def _get_lifecycle(database_engine: AsyncEngine) -> dict[str, datetime]:
    async with database_engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    SELECT first_seen_at, last_seen_at, last_changed_at
                    FROM economic_calendar_events
                    WHERE calendar_type = 'FOREX' AND external_event_id = '123'
                    """
                )
            )
        ).one()
    return {
        "first_seen_at": row.first_seen_at,
        "last_seen_at": row.last_seen_at,
        "last_changed_at": row.last_changed_at,
    }


async def _insert_event(
    connection: object,
    calendar_type: str,
    external_event_id: str,
    currency: str,
    impact: str,
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
                'Event',
                :currency,
                :impact,
                :scheduled_at
            )
            """
        ),
        {
            "calendar_type": calendar_type,
            "external_event_id": external_event_id,
            "currency": currency,
            "impact": impact,
            "scheduled_at": scheduled_at,
        },
    )
