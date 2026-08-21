from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import cache, lru_cache
from typing import Any, Protocol, cast
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal  # type: ignore[import-untyped]

from app.domain.symbols import SupportedSymbol

FOREX_ASSET_CLASS = "FOREX"
ETF_ASSET_CLASS = "ETF"
WTI_SYMBOL = "WTI"
XAU_SYMBOL = "XAU/USD"
INTERNAL_CALENDAR_SOURCE = "internal"
PANDAS_MARKET_CALENDAR_SOURCE = "pandas_market_calendars"
ALWAYS_OPEN_CALENDAR_NAME = "24/7"
FOREX_CALENDAR_NAME = "FOREX"
COARSE_TIMEFRAMES = frozenset({"1d", "1w"})
NEW_YORK = ZoneInfo("America/New_York")
FOREX_SESSION_BOUNDARY = time(hour=17)
ETF_SESSION_OPEN = time(hour=9, minute=30)
ETF_SESSION_CLOSE = time(hour=16)
WTI_SESSION_REOPEN = time(hour=18)
WTI_SESSION_CLOSE = time(hour=17)


class MarketSessionPolicy(Protocol):
    def is_eligible(self, open_time: datetime, timeframe: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class CalendarSession:
    session_date: date
    market_open: datetime
    market_close: datetime
    break_start: datetime | None
    break_end: datetime | None


class AlwaysOpenSessionPolicy:
    def is_eligible(self, open_time: datetime, timeframe: str) -> bool:
        del open_time, timeframe
        return True


class ForexWeeklySessionPolicy:
    def is_eligible(self, open_time: datetime, timeframe: str) -> bool:
        if timeframe == "1mo":
            return True
        if timeframe in COARSE_TIMEFRAMES:
            return open_time.astimezone(UTC).weekday() < 5

        local_open = open_time.astimezone(NEW_YORK)
        weekday = local_open.weekday()
        local_time = local_open.time().replace(tzinfo=None)
        if weekday < 4:
            return True
        if weekday == 4:
            return local_time < FOREX_SESSION_BOUNDARY
        if weekday == 5:
            return False
        return local_time >= FOREX_SESSION_BOUNDARY


class UsEtfRegularSessionPolicy:
    def is_eligible(self, open_time: datetime, timeframe: str) -> bool:
        if timeframe == "1mo":
            return True
        if timeframe in COARSE_TIMEFRAMES:
            return open_time.astimezone(UTC).weekday() < 5
        local_open = open_time.astimezone(NEW_YORK)
        return (
            local_open.weekday() < 5
            and ETF_SESSION_OPEN <= local_open.time().replace(tzinfo=None) < ETF_SESSION_CLOSE
        )


class WtiEnergySessionPolicy:
    def is_eligible(self, open_time: datetime, timeframe: str) -> bool:
        if timeframe == "1mo":
            return True
        if timeframe in COARSE_TIMEFRAMES:
            return open_time.astimezone(UTC).weekday() < 5
        local_open = open_time.astimezone(NEW_YORK)
        weekday = local_open.weekday()
        local_time = local_open.time().replace(tzinfo=None)
        if weekday == 5:
            return False
        if weekday == 6:
            return local_time >= WTI_SESSION_REOPEN
        if weekday == 4:
            return local_time < WTI_SESSION_CLOSE
        return local_time < WTI_SESSION_CLOSE or local_time >= WTI_SESSION_REOPEN


@dataclass(frozen=True, slots=True)
class PandasMarketCalendarSessionPolicy:
    calendar_name: str

    def is_eligible(self, open_time: datetime, timeframe: str) -> bool:
        open_time = open_time.astimezone(UTC)
        if timeframe == "1d":
            return any(
                session.session_date == open_time.date()
                for session in _calendar_sessions(
                    self.calendar_name,
                    open_time.date(),
                    open_time.date(),
                )
            )
        if timeframe == "1w":
            return bool(
                _calendar_sessions(
                    self.calendar_name,
                    open_time.date(),
                    open_time.date() + timedelta(days=6),
                )
            )
        if timeframe == "1mo":
            next_month = date(open_time.year + (open_time.month == 12), open_time.month % 12 + 1, 1)
            return bool(
                _calendar_sessions(
                    self.calendar_name,
                    open_time.date(),
                    next_month - timedelta(days=1),
                )
            )

        return any(
            session.market_open <= open_time < session.market_close
            and not (
                session.break_start is not None
                and session.break_end is not None
                and session.break_start <= open_time < session.break_end
            )
            for session in _calendar_sessions(
                self.calendar_name,
                open_time.date() - timedelta(days=1),
                open_time.date() + timedelta(days=1),
            )
        )


ALWAYS_OPEN_SESSION = AlwaysOpenSessionPolicy()
FOREX_WEEKLY_SESSION = ForexWeeklySessionPolicy()
US_ETF_REGULAR_SESSION = UsEtfRegularSessionPolicy()
WTI_ENERGY_SESSION = WtiEnergySessionPolicy()


def get_market_session_policy(symbol: SupportedSymbol) -> MarketSessionPolicy:
    if symbol.calendar_source == INTERNAL_CALENDAR_SOURCE:
        if symbol.calendar_name == ALWAYS_OPEN_CALENDAR_NAME:
            return ALWAYS_OPEN_SESSION
    if symbol.calendar_source == PANDAS_MARKET_CALENDAR_SOURCE and symbol.calendar_name:
        if symbol.calendar_name == FOREX_CALENDAR_NAME or symbol.symbol == XAU_SYMBOL:
            return FOREX_WEEKLY_SESSION
        if _calendar_exists(symbol.calendar_name):
            return PandasMarketCalendarSessionPolicy(symbol.calendar_name)
    if symbol.symbol == WTI_SYMBOL:
        return WTI_ENERGY_SESSION
    return get_market_session_policy_for_asset_class(symbol.asset_class)


def get_market_session_policy_for_asset_class(asset_class: str) -> MarketSessionPolicy:
    if asset_class == FOREX_ASSET_CLASS:
        return FOREX_WEEKLY_SESSION
    if asset_class == ETF_ASSET_CLASS:
        return US_ETF_REGULAR_SESSION
    return ALWAYS_OPEN_SESSION


@cache
def _calendar_exists(calendar_name: str) -> bool:
    try:
        _calendar(calendar_name)
    except RuntimeError:
        return False
    return True


@cache
def _calendar(calendar_name: str) -> Any:
    return mcal.get_calendar(calendar_name)


@lru_cache(maxsize=32)
def _calendar_year_sessions(calendar_name: str, year: int) -> tuple[CalendarSession, ...]:
    schedule = _calendar(calendar_name).schedule(
        start_date=date(year, 1, 1),
        end_date=date(year, 12, 31),
    )
    sessions: list[CalendarSession] = []
    for session_date, row in schedule.iterrows():
        break_start = row.get("break_start")
        break_end = row.get("break_end")
        sessions.append(
            CalendarSession(
                session_date=cast(date, session_date.date()),
                market_open=cast(datetime, row["market_open"].to_pydatetime()).astimezone(UTC),
                market_close=cast(datetime, row["market_close"].to_pydatetime()).astimezone(UTC),
                break_start=(
                    None
                    if break_start is None
                    else cast(datetime, break_start.to_pydatetime()).astimezone(UTC)
                ),
                break_end=(
                    None
                    if break_end is None
                    else cast(datetime, break_end.to_pydatetime()).astimezone(UTC)
                ),
            )
        )
    return tuple(sessions)


@lru_cache(maxsize=4096)
def _calendar_sessions(
    calendar_name: str,
    start_date: date,
    end_date: date,
) -> tuple[CalendarSession, ...]:
    if end_date < start_date:
        return ()
    sessions: list[CalendarSession] = []
    for year in range(start_date.year, end_date.year + 1):
        sessions.extend(
            session
            for session in _calendar_year_sessions(calendar_name, year)
            if start_date <= session.session_date <= end_date
        )
    return tuple(sessions)
