from datetime import UTC, datetime, time
from typing import Protocol
from zoneinfo import ZoneInfo

from app.domain.symbols import SupportedSymbol

FOREX_ASSET_CLASS = "FOREX"
ETF_ASSET_CLASS = "ETF"
WTI_SYMBOL = "WTI"
DAILY_TIMEFRAME = "1d"
NEW_YORK = ZoneInfo("America/New_York")
FOREX_SESSION_BOUNDARY = time(hour=17)
ETF_SESSION_OPEN = time(hour=9, minute=30)
ETF_SESSION_CLOSE = time(hour=16)
WTI_SESSION_REOPEN = time(hour=18)
WTI_SESSION_CLOSE = time(hour=17)


class MarketSessionPolicy(Protocol):
    def is_eligible(self, open_time: datetime, timeframe: str) -> bool: ...


class AlwaysOpenSessionPolicy:
    def is_eligible(self, open_time: datetime, timeframe: str) -> bool:
        del open_time, timeframe
        return True


class ForexWeeklySessionPolicy:
    def is_eligible(self, open_time: datetime, timeframe: str) -> bool:
        if timeframe == DAILY_TIMEFRAME:
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
        if timeframe == DAILY_TIMEFRAME:
            return open_time.astimezone(UTC).weekday() < 5
        local_open = open_time.astimezone(NEW_YORK)
        return (
            local_open.weekday() < 5
            and ETF_SESSION_OPEN <= local_open.time().replace(tzinfo=None) < ETF_SESSION_CLOSE
        )


class WtiEnergySessionPolicy:
    def is_eligible(self, open_time: datetime, timeframe: str) -> bool:
        if timeframe == DAILY_TIMEFRAME:
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


ALWAYS_OPEN_SESSION = AlwaysOpenSessionPolicy()
FOREX_WEEKLY_SESSION = ForexWeeklySessionPolicy()
US_ETF_REGULAR_SESSION = UsEtfRegularSessionPolicy()
WTI_ENERGY_SESSION = WtiEnergySessionPolicy()


def get_market_session_policy(symbol: SupportedSymbol) -> MarketSessionPolicy:
    if symbol.symbol == WTI_SYMBOL:
        return WTI_ENERGY_SESSION
    return get_market_session_policy_for_asset_class(symbol.asset_class)


def get_market_session_policy_for_asset_class(asset_class: str) -> MarketSessionPolicy:
    if asset_class == FOREX_ASSET_CLASS:
        return FOREX_WEEKLY_SESSION
    if asset_class == ETF_ASSET_CLASS:
        return US_ETF_REGULAR_SESSION
    return ALWAYS_OPEN_SESSION
