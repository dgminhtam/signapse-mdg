from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.domain.market_sessions import (
    ALWAYS_OPEN_SESSION,
    FOREX_WEEKLY_SESSION,
    get_market_session_policy,
)
from app.domain.symbols import SupportedSymbol

EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True)
BTC = SupportedSymbol("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True)


@pytest.mark.parametrize(
    ("open_time", "eligible"),
    [
        (datetime(2026, 6, 19, 20, 59, tzinfo=UTC), True),
        (datetime(2026, 6, 19, 21, 0, tzinfo=UTC), False),
        (datetime(2026, 6, 21, 20, 59, tzinfo=UTC), False),
        (datetime(2026, 6, 21, 21, 0, tzinfo=UTC), True),
        (datetime(2026, 1, 9, 21, 59, tzinfo=UTC), True),
        (datetime(2026, 1, 9, 22, 0, tzinfo=UTC), False),
        (datetime(2026, 1, 11, 21, 59, tzinfo=UTC), False),
        (datetime(2026, 1, 11, 22, 0, tzinfo=UTC), True),
    ],
)
def test_forex_intraday_session_tracks_new_york_dst(
    open_time: datetime,
    eligible: bool,
) -> None:
    assert FOREX_WEEKLY_SESSION.is_eligible(open_time, "1h") is eligible


@pytest.mark.parametrize(
    ("open_time", "eligible"),
    [
        (datetime(2026, 6, 19, tzinfo=UTC), True),
        (datetime(2026, 6, 20, tzinfo=UTC), False),
        (datetime(2026, 6, 21, tzinfo=UTC), False),
        (datetime(2026, 6, 22, tzinfo=UTC), True),
    ],
)
def test_forex_daily_session_uses_utc_weekday_label(
    open_time: datetime,
    eligible: bool,
) -> None:
    assert FOREX_WEEKLY_SESSION.is_eligible(open_time, "1d") is eligible


def test_forex_daily_session_normalizes_to_utc_before_weekday_check() -> None:
    local_friday_that_is_utc_saturday = datetime(
        2026,
        6,
        19,
        20,
        0,
        tzinfo=ZoneInfo("America/New_York"),
    )

    assert FOREX_WEEKLY_SESSION.is_eligible(local_friday_that_is_utc_saturday, "1d") is False


def test_policy_selection_uses_persisted_asset_class() -> None:
    assert get_market_session_policy(EUR) is FOREX_WEEKLY_SESSION
    assert get_market_session_policy(BTC) is ALWAYS_OPEN_SESSION
