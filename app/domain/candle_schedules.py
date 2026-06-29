from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.domain.market_sessions import MarketSessionPolicy
from app.domain.symbols import SupportedSymbol
from app.domain.timeframes import EPOCH, Timeframe, add_month, month_opens

TWELVEDATA_OFFSET_HOURLY_SYMBOLS = frozenset({"WTI", "SPY", "QQQ"})


@dataclass(frozen=True, slots=True)
class ProviderFetchSection:
    start: datetime
    end: datetime
    expected_count: int


class CandleSchedule(Protocol):
    def expected_opens(
        self,
        start: datetime,
        end: datetime,
        policy: MarketSessionPolicy,
        timeframe: str,
    ) -> tuple[datetime, ...]: ...

    def missing_sections(
        self,
        expected_opens: tuple[datetime, ...],
        available_opens: set[datetime],
    ) -> tuple[ProviderFetchSection, ...]: ...


@dataclass(frozen=True, slots=True)
class FixedOffsetCandleSchedule:
    duration: timedelta
    offset: timedelta = timedelta(0)

    def expected_opens(
        self,
        start: datetime,
        end: datetime,
        policy: MarketSessionPolicy,
        timeframe: str,
    ) -> tuple[datetime, ...]:
        cursor = self._first_open_at_or_after(start)
        opens: list[datetime] = []
        while cursor < end:
            if policy.is_eligible(cursor, timeframe):
                opens.append(cursor)
            cursor += self.duration
        return tuple(opens)

    def missing_sections(
        self,
        expected_opens: tuple[datetime, ...],
        available_opens: set[datetime],
    ) -> tuple[ProviderFetchSection, ...]:
        missing = [value for value in expected_opens if value not in available_opens]
        if not missing:
            return ()
        sections: list[ProviderFetchSection] = []
        section_start = missing[0]
        previous = missing[0]
        count = 1
        for value in missing[1:]:
            if value == previous + self.duration:
                previous = value
                count += 1
                continue
            sections.append(
                ProviderFetchSection(
                    start=section_start,
                    end=previous + self.duration,
                    expected_count=count,
                )
            )
            section_start = value
            previous = value
            count = 1
        sections.append(
            ProviderFetchSection(
                start=section_start,
                end=previous + self.duration,
                expected_count=count,
            )
        )
        return tuple(sections)

    def _first_open_at_or_after(self, value: datetime) -> datetime:
        anchor = EPOCH + self.offset
        elapsed = value - anchor
        steps = elapsed // self.duration
        candidate = anchor + steps * self.duration
        if candidate < value:
            candidate += self.duration
        return candidate


class CalendarMonthCandleSchedule:
    def expected_opens(
        self,
        start: datetime,
        end: datetime,
        policy: MarketSessionPolicy,
        timeframe: str,
    ) -> tuple[datetime, ...]:
        return tuple(
            value for value in month_opens(start, end) if policy.is_eligible(value, timeframe)
        )

    def missing_sections(
        self,
        expected_opens: tuple[datetime, ...],
        available_opens: set[datetime],
    ) -> tuple[ProviderFetchSection, ...]:
        missing = [value for value in expected_opens if value not in available_opens]
        if not missing:
            return ()
        sections: list[ProviderFetchSection] = []
        section_start = previous = missing[0]
        count = 1
        for value in missing[1:]:
            if value == add_month(previous):
                previous = value
                count += 1
                continue
            sections.append(ProviderFetchSection(section_start, add_month(previous), count))
            section_start = previous = value
            count = 1
        sections.append(ProviderFetchSection(section_start, add_month(previous), count))
        return tuple(sections)


def get_candle_schedule(
    symbol: SupportedSymbol,
    timeframe: Timeframe,
) -> CandleSchedule:
    if timeframe.calendar_month:
        return CalendarMonthCandleSchedule()
    offset = timedelta(0)
    if (
        symbol.provider == "TWELVE_DATA"
        and symbol.provider_symbol in TWELVEDATA_OFFSET_HOURLY_SYMBOLS
        and timeframe.value == "1h"
    ):
        offset = timedelta(minutes=30)
    if timeframe.value == "1w":
        offset = timedelta(days=4)
    return FixedOffsetCandleSchedule(timeframe.duration, offset)
