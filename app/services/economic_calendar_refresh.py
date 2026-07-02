from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.core.cronjob import Cronjob
from app.domain.economic_calendar import EconomicCalendarProvider, EconomicCalendarRepository

CALENDAR_TYPES = ("FOREX", "METALS", "ENERGY", "CRYPTO")
LOOKBACK_DAYS = 2
LOOKAHEAD_DAYS = 7


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
        today = self._clock().astimezone(UTC).replace(
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
