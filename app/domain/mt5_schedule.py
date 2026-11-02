from datetime import datetime, timedelta

from app.domain.candle_schedules import (
    CalendarMonthCandleSchedule,
    FixedOffsetCandleSchedule,
    ProviderFetchSection,
)
from app.domain.market_sessions import ALWAYS_OPEN_SESSION, MarketSessionPolicy
from app.domain.mt5_time import from_broker_wall, to_broker_wall
from app.domain.timeframes import Timeframe


class BrokerCandleSchedule:
    """Preserve native broker buckets, including daily/weekly/monthly DST boundaries."""

    def __init__(self, timeframe: Timeframe) -> None:
        self._native = (
            CalendarMonthCandleSchedule()
            if timeframe.calendar_month
            else FixedOffsetCandleSchedule(
                timeframe.duration, timedelta(days=3) if timeframe.value == "1w" else timedelta()
            )
        )

    def expected_opens(
        self, start: datetime, end: datetime, policy: MarketSessionPolicy, timeframe: str
    ) -> tuple[datetime, ...]:
        return tuple(
            from_broker_wall(t, nominal=True)
            for t in self._native.expected_opens(
                to_broker_wall(start), to_broker_wall(end), ALWAYS_OPEN_SESSION, timeframe
            )
        )

    def latest_opens(
        self, end: datetime, limit: int, policy: MarketSessionPolicy, timeframe: str
    ) -> tuple[datetime, ...]:
        return tuple(
            from_broker_wall(t, nominal=True)
            for t in self._native.latest_opens(
                to_broker_wall(end), limit, ALWAYS_OPEN_SESSION, timeframe
            )
        )

    def next_opens(
        self, start: datetime, limit: int, policy: MarketSessionPolicy, timeframe: str
    ) -> tuple[datetime, ...]:
        return tuple(
            from_broker_wall(t, nominal=True)
            for t in self._native.next_opens(
                to_broker_wall(start), limit, ALWAYS_OPEN_SESSION, timeframe
            )
        )

    def end_after(self, open_time: datetime) -> datetime:
        return from_broker_wall(self._native.end_after(to_broker_wall(open_time)), nominal=True)

    def missing_sections(
        self, expected_opens: tuple[datetime, ...], available_opens: set[datetime]
    ) -> tuple[ProviderFetchSection, ...]:
        sections = self._native.missing_sections(
            tuple(to_broker_wall(t) for t in expected_opens),
            {to_broker_wall(t) for t in available_opens},
        )
        return tuple(
            ProviderFetchSection(
                from_broker_wall(s.start, nominal=True),
                from_broker_wall(s.end, nominal=True),
                s.expected_count,
            )
            for s in sections
        )
