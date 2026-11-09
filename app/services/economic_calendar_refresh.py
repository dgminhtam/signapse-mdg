import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.core.cronjob import Cronjob
from app.core.observability import log_event
from app.domain.economic_calendar import EconomicCalendarProvider, EconomicCalendarRepository

CALENDAR_TYPES = ("FOREX",)
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
        _log_refresh_completed(provider_rows=len(events), started=started)


def _log_refresh_completed(
    *,
    provider_rows: int,
    started: float,
) -> None:
    log_event(
        logger,
        logging.INFO,
        "economic_calendar_refresh_completed",
        operation="economic_calendar.refresh",
        provider="MT5_CALENDAR",
        provider_rows=provider_rows,
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
