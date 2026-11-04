from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EconomicCalendarEvent:
    calendar_type: str
    external_event_id: str
    name: str
    currency: str | None
    impact: str | None
    scheduled_at: datetime
    actual: str | None
    forecast: str | None
    previous: str | None
    revision: str | None
    actual_better_worse: str | None
    revision_better_worse: str | None
    description: str | None
    news_url: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_changed_at: datetime


@dataclass(frozen=True, slots=True)
class EconomicCalendarFetchedEvent:
    calendar_type: str
    external_event_id: str
    name: str
    currency: str | None
    impact: str | None
    scheduled_at: datetime
    actual: str | None
    forecast: str | None
    previous: str | None
    revision: str | None
    actual_better_worse: str | None
    revision_better_worse: str | None
    description: str | None = None
    news_url: str | None = None


@dataclass(frozen=True, slots=True)
class EconomicCalendarEnrichmentCandidate:
    calendar_type: str
    external_event_id: str


@dataclass(frozen=True, slots=True)
class EconomicCalendarEnrichment:
    calendar_type: str
    external_event_id: str
    description: str | None
    news_url: str | None


@dataclass(frozen=True, slots=True)
class EconomicCalendarRequest:
    start: datetime
    end: datetime
    types: tuple[str, ...]
    currencies: tuple[str, ...]
    impact: tuple[str, ...]
    limit: int


@dataclass(frozen=True, slots=True)
class EconomicCalendarResult:
    start: datetime
    end: datetime
    events: list[EconomicCalendarEvent]


class EconomicCalendarRepository(Protocol):
    async def list_events(
        self,
        request: EconomicCalendarRequest,
    ) -> list[EconomicCalendarEvent]: ...

    async def upsert_events(self, events: list[EconomicCalendarFetchedEvent]) -> None: ...

    async def claim_enrichment_candidates(
        self,
        start: datetime,
        end: datetime,
        attempted_at: datetime,
    ) -> list[EconomicCalendarEnrichmentCandidate]: ...

    async def update_enrichments(
        self,
        enrichments: list[EconomicCalendarEnrichment],
    ) -> None: ...


class EconomicCalendarProvider(Protocol):
    async def fetch_events(
        self,
        calendar_type: str,
        start: datetime,
        end: datetime,
    ) -> list[EconomicCalendarFetchedEvent]: ...
