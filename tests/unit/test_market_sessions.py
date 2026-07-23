from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.domain import market_sessions as session_module
from app.domain.market_sessions import (
    ALWAYS_OPEN_SESSION,
    FOREX_WEEKLY_SESSION,
    US_ETF_REGULAR_SESSION,
    WTI_ENERGY_SESSION,
    CalendarSession,
    PandasMarketCalendarSessionPolicy,
    get_market_session_policy,
)
from app.domain.symbols import SupportedSymbol

EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True)
BTC = SupportedSymbol("BTC/USD", "CRYPTO", "TWELVE_DATA", "BTC/USD", True)
SPY = SupportedSymbol("SPY", "ETF", "TWELVE_DATA", "SPY", True)
WTI = SupportedSymbol("WTI", "COMMODITY", "TWELVE_DATA", "WTI", True)
XAU = SupportedSymbol("XAU/USD", "COMMODITY", "TWELVE_DATA", "XAU/USD", True)
BTC_247 = SupportedSymbol(
    "BTC/USD",
    "CRYPTO",
    "TWELVE_DATA",
    "BTC/USD",
    True,
    "internal",
    "24/7",
    "UTC",
)
SPY_NYSE = SupportedSymbol(
    "SPY",
    "ETF",
    "TWELVE_DATA",
    "SPY",
    True,
    "pandas_market_calendars",
    "NYSE",
    "America/New_York",
)
XAU_FOREX = SupportedSymbol(
    "XAU/USD",
    "COMMODITY",
    "TWELVE_DATA",
    "XAU/USD",
    True,
    "pandas_market_calendars",
    "FOREX",
    "America/New_York",
)


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
        (datetime(2026, 6, 19, 20, 0, tzinfo=UTC), True),
        (datetime(2026, 6, 20, 0, 0, tzinfo=UTC), False),
    ],
)
@pytest.mark.parametrize("timeframe", ["1h", "4h"])
def test_forex_intraday_session_tracks_new_york_dst(
    open_time: datetime,
    eligible: bool,
    timeframe: str,
) -> None:
    assert FOREX_WEEKLY_SESSION.is_eligible(open_time, timeframe) is eligible


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


def test_policy_selection_prefers_inline_calendar_config() -> None:
    assert get_market_session_policy(BTC_247) is ALWAYS_OPEN_SESSION
    assert isinstance(get_market_session_policy(SPY_NYSE), PandasMarketCalendarSessionPolicy)
    assert get_market_session_policy(XAU_FOREX) is FOREX_WEEKLY_SESSION


def test_policy_selection_falls_back_for_unsupported_inline_calendar() -> None:
    symbol = SupportedSymbol(
        "SPY",
        "ETF",
        "TWELVE_DATA",
        "SPY",
        True,
        "pandas_market_calendars",
        "MISSING_CALENDAR",
        "UTC",
    )

    assert get_market_session_policy(symbol) is US_ETF_REGULAR_SESSION


@pytest.mark.parametrize(
    ("open_time", "timeframe", "eligible"),
    [
        (datetime(2026, 7, 2, 14, 0, tzinfo=UTC), "1h", True),
        (datetime(2026, 7, 3, 14, 0, tzinfo=UTC), "1h", False),
        (datetime(2026, 7, 2, 16, 0, tzinfo=UTC), "4h", True),
        (datetime(2026, 7, 3, 16, 0, tzinfo=UTC), "4h", False),
        (datetime(2026, 7, 2, tzinfo=UTC), "1d", True),
        (datetime(2026, 7, 3, tzinfo=UTC), "1d", False),
    ],
)
def test_pandas_calendar_policy_uses_exchange_sessions(
    open_time: datetime,
    timeframe: str,
    eligible: bool,
) -> None:
    assert get_market_session_policy(SPY_NYSE).is_eligible(open_time, timeframe) is eligible


def test_pandas_calendar_policy_excludes_break_window(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_sessions(
        calendar_name: str,
        start_date: object,
        end_date: object,
    ) -> tuple[CalendarSession, ...]:
        del calendar_name, start_date, end_date
        return (
            CalendarSession(
                datetime(2026, 6, 22, tzinfo=UTC).date(),
                datetime(2026, 6, 22, 13, 0, tzinfo=UTC),
                datetime(2026, 6, 22, 21, 0, tzinfo=UTC),
                datetime(2026, 6, 22, 16, 0, tzinfo=UTC),
                datetime(2026, 6, 22, 17, 0, tzinfo=UTC),
            ),
        )

    monkeypatch.setattr(session_module, "_calendar_sessions", fake_sessions)
    policy = PandasMarketCalendarSessionPolicy("TEST")

    assert policy.is_eligible(datetime(2026, 6, 22, 15, 59, tzinfo=UTC), "1m") is True
    assert policy.is_eligible(datetime(2026, 6, 22, 16, 30, tzinfo=UTC), "1m") is False
    assert policy.is_eligible(datetime(2026, 6, 22, 17, 0, tzinfo=UTC), "1m") is True


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
