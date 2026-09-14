import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.core.cronjob import Cronjob
from app.core.observability import log_event
from app.domain.economic_calendar import EconomicCalendarProvider, EconomicCalendarRepository

CALENDAR_TYPES = ("FOREX", "METALS", "ENERGY", "CRYPTO")
LOOKBACK_DAYS = 2
LOOKAHEAD_DAYS = 7

logger = logging.getLogger(__name__)


class EconomicCalendarRefreshService:
    def __init__(
        self,
        provider: EconomicCalendarProvider,
        repository: EconomicCalendarRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))

    async def refresh(self) -> None:
        started = time.perf_counter()
        now = self._clock().astimezone(UTC)
        today = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        start = today - timedelta(days=LOOKBACK_DAYS)
        end = today + timedelta(days=LOOKAHEAD_DAYS)
        events = []
        for calendar_type in CALENDAR_TYPES:
            events.extend(await self._provider.fetch_events(calendar_type, start, end))
        await self._repository.upsert_events(events)
        candidates = await self._repository.claim_enrichment_candidates(start, end, now)
        if not candidates:
            _log_refresh_completed(
                provider_rows=len(events),
                enrichment_candidates=0,
                enrichment_rows=0,
                started=started,
            )
            return
        enrichments = await self._provider.fetch_event_details(candidates)
        await self._repository.update_enrichments(enrichments)
        _log_refresh_completed(
            provider_rows=len(events),
            enrichment_candidates=len(candidates),
            enrichment_rows=len(enrichments),
            started=started,
        )


def _log_refresh_completed(
    *,
    provider_rows: int,
    enrichment_candidates: int,
    enrichment_rows: int,
    started: float,
) -> None:
    failed_count = enrichment_candidates - enrichment_rows
    log_event(
        logger,
        logging.WARNING if failed_count else logging.INFO,
        "economic_calendar_refresh_completed",
        operation="economic_calendar.refresh",
        provider="MARKET_CALENDAR",
        provider_rows=provider_rows,
        enrichment_candidates=enrichment_candidates,
        enrichment_rows=enrichment_rows,
        failed_count=failed_count,
        partial=bool(failed_count),
        latency_ms=round((time.perf_counter() - started) * 1000, 3),
    )


class EconomicCalendarFetchCronjob(Cronjob):
    def __init__(
        self,
        service: EconomicCalendarRefreshService,
        *,
        interval_seconds: float,
    ) -> None:
        super().__init__(
            name="economic-calendar-refresh",
            interval_seconds=interval_seconds,
            run_on_start=True,
        )
        self._service = service

    async def run_once(self) -> None:
        await self._service.refresh()
