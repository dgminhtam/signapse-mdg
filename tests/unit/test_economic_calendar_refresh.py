from datetime import UTC, datetime

from app.domain.economic_calendar import (
    EconomicCalendarEnrichment,
    EconomicCalendarEnrichmentCandidate,
    EconomicCalendarFetchedEvent,
)
from app.services.economic_calendar_refresh import (
    CALENDAR_TYPES,
    EconomicCalendarFetchCronjob,
    EconomicCalendarRefreshService,
)


class FakeProvider:
    def __init__(
        self,
        details: list[EconomicCalendarEnrichment] | None = None,
        actions: list[str] | None = None,
    ) -> None:
        self.calls: list[tuple[str, datetime, datetime]] = []
        self.detail_calls: list[list[EconomicCalendarEnrichmentCandidate]] = []
        self.details = details or []
        self.actions = actions

    async def fetch_events(
        self,
        calendar_type: str,
        start: datetime,
        end: datetime,
    ) -> list[EconomicCalendarFetchedEvent]:
        self.calls.append((calendar_type, start, end))
        return [
            EconomicCalendarFetchedEvent(
                calendar_type=calendar_type,
                external_event_id=f"{calendar_type}-1",
                name="Event",
                currency="USD",
                impact="high",
                scheduled_at=start,
                actual=None,
                forecast=None,
                previous=None,
                revision=None,
                actual_better_worse=None,
                revision_better_worse=None,
            )
        ]

    async def fetch_event_details(
        self,
        candidates: list[EconomicCalendarEnrichmentCandidate],
    ) -> list[EconomicCalendarEnrichment]:
        self.detail_calls.append(candidates)
        if self.actions is not None:
            self.actions.append("fetch_details")
        return self.details


class FakeRepository:
    def __init__(
        self,
        candidates: list[EconomicCalendarEnrichmentCandidate] | None = None,
        actions: list[str] | None = None,
    ) -> None:
        self.upserted: list[EconomicCalendarFetchedEvent] = []
        self.candidates = candidates or []
        self.claims: list[tuple[datetime, datetime, datetime]] = []
        self.enrichments: list[EconomicCalendarEnrichment] = []
        self.actions = actions

    async def list_events(self, request: object) -> list[object]:
        del request
        return []

    async def upsert_events(self, events: list[EconomicCalendarFetchedEvent]) -> None:
        self.upserted.extend(events)
        if self.actions is not None:
            self.actions.append("upsert")

    async def claim_enrichment_candidates(
        self,
        start: datetime,
        end: datetime,
        attempted_at: datetime,
    ) -> list[EconomicCalendarEnrichmentCandidate]:
        self.claims.append((start, end, attempted_at))
        if self.actions is not None:
            self.actions.append("claim")
        return self.candidates

    async def update_enrichments(
        self,
        enrichments: list[EconomicCalendarEnrichment],
    ) -> None:
        self.enrichments.extend(enrichments)
        if self.actions is not None:
            self.actions.append("update")


async def test_refresh_service_fetches_fixed_window_and_types() -> None:
    provider = FakeProvider()
    repository = FakeRepository()
    service = EconomicCalendarRefreshService(
        provider,
        repository,
        clock=lambda: datetime(2026, 7, 10, 15, 45, tzinfo=UTC),
    )

    await service.refresh()

    assert [call[0] for call in provider.calls] == list(CALENDAR_TYPES)
    assert all(call[1] == datetime(2026, 7, 8, tzinfo=UTC) for call in provider.calls)
    assert all(call[2] == datetime(2026, 7, 17, tzinfo=UTC) for call in provider.calls)
    assert [event.calendar_type for event in repository.upserted] == list(CALENDAR_TYPES)
    assert repository.claims == []
    assert provider.detail_calls == []


async def test_refresh_does_not_request_missing_mt5_descriptions() -> None:
    provider = FakeProvider()
    repository = FakeRepository([EconomicCalendarEnrichmentCandidate("FOREX", "old")])
    await EconomicCalendarRefreshService(provider, repository).refresh()
    assert provider.detail_calls == []
    assert repository.claims == []
    assert repository.enrichments == []


async def test_economic_calendar_fetch_cronjob_runs_refresh_service() -> None:
    provider = FakeProvider()
    repository = FakeRepository()
    service = EconomicCalendarRefreshService(provider, repository)
    job = EconomicCalendarFetchCronjob(service, interval_seconds=300)

    await job.run_once()

    assert job.name == "economic-calendar-refresh"
    assert job.interval_seconds == 300
    assert job.run_on_start is True
    assert len(repository.upserted) == len(CALENDAR_TYPES)
