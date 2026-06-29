from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.domain.market_sessions import (
    ALWAYS_OPEN_SESSION,
    FOREX_WEEKLY_SESSION,
    US_ETF_REGULAR_SESSION,
    WTI_ENERGY_SESSION,
    get_market_session_policy,
)
from app.domain.symbols import SupportedSymbol

EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True)
BTC = SupportedSymbol("BTC/USD", "CRYPTO", "TWELVE_DATA", "BTC/USD", True)
SPY = SupportedSymbol("SPY", "ETF", "TWELVE_DATA", "SPY", True)
WTI = SupportedSymbol("WTI", "COMMODITY", "TWELVE_DATA", "WTI", True)
XAU = SupportedSymbol("XAU/USD", "COMMODITY", "TWELVE_DATA", "XAU/USD", True)


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
    assert get_market_session_policy(SPY) is US_ETF_REGULAR_SESSION
    assert get_market_session_policy(WTI) is WTI_ENERGY_SESSION
    assert get_market_session_policy(XAU) is ALWAYS_OPEN_SESSION


@pytest.mark.parametrize(
    ("open_time", "eligible"),
    [
        (datetime(2026, 6, 22, 13, 29, tzinfo=UTC), False),
        (datetime(2026, 6, 22, 13, 30, tzinfo=UTC), True),
        (datetime(2026, 6, 22, 19, 59, tzinfo=UTC), True),
        (datetime(2026, 6, 22, 20, 0, tzinfo=UTC), False),
        (datetime(2026, 1, 12, 14, 29, tzinfo=UTC), False),
        (datetime(2026, 1, 12, 14, 30, tzinfo=UTC), True),
        (datetime(2026, 6, 20, 14, 0, tzinfo=UTC), False),
    ],
)
def test_etf_regular_session_tracks_new_york_dst(
    open_time: datetime,
    eligible: bool,
) -> None:
    assert US_ETF_REGULAR_SESSION.is_eligible(open_time, "1m") is eligible


@pytest.mark.parametrize(
    ("open_time", "eligible"),
    [
        (datetime(2026, 6, 19, 20, 59, tzinfo=UTC), True),
        (datetime(2026, 6, 19, 21, 0, tzinfo=UTC), False),
        (datetime(2026, 6, 21, 21, 59, tzinfo=UTC), False),
        (datetime(2026, 6, 21, 22, 0, tzinfo=UTC), True),
        (datetime(2026, 6, 22, 20, 59, tzinfo=UTC), True),
        (datetime(2026, 6, 22, 21, 0, tzinfo=UTC), False),
        (datetime(2026, 6, 22, 22, 0, tzinfo=UTC), True),
        (datetime(2026, 1, 11, 22, 59, tzinfo=UTC), False),
        (datetime(2026, 1, 11, 23, 0, tzinfo=UTC), True),
    ],
)
def test_wti_energy_session_tracks_weekly_and_maintenance_boundaries(
    open_time: datetime,
    eligible: bool,
) -> None:
    assert WTI_ENERGY_SESSION.is_eligible(open_time, "1h") is eligible


@pytest.mark.parametrize("policy", [US_ETF_REGULAR_SESSION, WTI_ENERGY_SESSION])
def test_new_market_daily_sessions_use_utc_weekday_labels(policy: object) -> None:
    assert policy.is_eligible(datetime(2026, 6, 19, tzinfo=UTC), "1d") is True
    assert policy.is_eligible(datetime(2026, 6, 20, tzinfo=UTC), "1d") is False
