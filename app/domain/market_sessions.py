from datetime import UTC, datetime, time
from typing import Protocol
from zoneinfo import ZoneInfo

from app.domain.symbols import SupportedSymbol

FOREX_ASSET_CLASS = "FOREX"
DAILY_TIMEFRAME = "1d"
NEW_YORK = ZoneInfo("America/New_York")
FOREX_SESSION_BOUNDARY = time(hour=17)


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


ALWAYS_OPEN_SESSION = AlwaysOpenSessionPolicy()
FOREX_WEEKLY_SESSION = ForexWeeklySessionPolicy()


def get_market_session_policy(symbol: SupportedSymbol) -> MarketSessionPolicy:
    return get_market_session_policy_for_asset_class(symbol.asset_class)


def get_market_session_policy_for_asset_class(asset_class: str) -> MarketSessionPolicy:
    if asset_class == FOREX_ASSET_CLASS:
        return FOREX_WEEKLY_SESSION
    return ALWAYS_OPEN_SESSION
