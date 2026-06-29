from datetime import UTC, datetime, timedelta

from app.domain.candle_schedules import ProviderFetchSection, get_candle_schedule
from app.domain.market_sessions import get_market_session_policy
from app.domain.symbols import SupportedSymbol
from app.domain.timeframes import get_timeframe

BTC = SupportedSymbol("BTC/USD", "CRYPTO", "TWELVE_DATA", "BTC/USD", True)
SPY = SupportedSymbol("SPY", "ETF", "TWELVE_DATA", "SPY", True)
WTI = SupportedSymbol("WTI", "COMMODITY", "TWELVE_DATA", "WTI", True)


def expected_opens(
    symbol: SupportedSymbol,
    timeframe_value: str,
    start: datetime,
    end: datetime,
) -> tuple[datetime, ...]:
    timeframe = get_timeframe(timeframe_value)
    assert timeframe is not None
    return get_candle_schedule(symbol, timeframe).expected_opens(
        start,
        end,
        get_market_session_policy(symbol),
        timeframe_value,
    )


def test_epoch_schedule_accepts_partial_public_range() -> None:
    start = datetime(2026, 6, 22, 10, 0, 30, tzinfo=UTC)
    end = datetime(2026, 6, 22, 10, 3, 15, tzinfo=UTC)

    assert expected_opens(BTC, "1m", start, end) == (
        datetime(2026, 6, 22, 10, 1, tzinfo=UTC),
        datetime(2026, 6, 22, 10, 2, tzinfo=UTC),
        datetime(2026, 6, 22, 10, 3, tzinfo=UTC),
    )


def test_twelvedata_hourly_schedule_uses_verified_minute_thirty_anchor() -> None:
    start = datetime(2026, 6, 22, 13, 0, tzinfo=UTC)
    end = datetime(2026, 6, 22, 16, 0, tzinfo=UTC)

    assert expected_opens(SPY, "1h", start, end) == (
        datetime(2026, 6, 22, 13, 30, tzinfo=UTC),
        datetime(2026, 6, 22, 14, 30, tzinfo=UTC),
        datetime(2026, 6, 22, 15, 30, tzinfo=UTC),
    )


def test_twelvedata_non_hourly_schedules_keep_verified_epoch_anchor() -> None:
    start = datetime(2026, 6, 22, 13, 31, tzinfo=UTC)
    end = datetime(2026, 6, 22, 13, 46, tzinfo=UTC)

    assert expected_opens(SPY, "5m", start, end) == (
        datetime(2026, 6, 22, 13, 35, tzinfo=UTC),
        datetime(2026, 6, 22, 13, 40, tzinfo=UTC),
        datetime(2026, 6, 22, 13, 45, tzinfo=UTC),
    )


def test_weekly_schedule_uses_monday_utc_anchor() -> None:
    start = datetime(2026, 6, 18, tzinfo=UTC)
    end = datetime(2026, 7, 1, tzinfo=UTC)

    assert expected_opens(BTC, "1w", start, end) == (
        datetime(2026, 6, 22, tzinfo=UTC),
        datetime(2026, 6, 29, tzinfo=UTC),
    )


def test_monthly_schedule_uses_calendar_month_opens() -> None:
    start = datetime(2026, 1, 15, tzinfo=UTC)
    end = datetime(2026, 4, 2, tzinfo=UTC)

    assert expected_opens(BTC, "1mo", start, end) == (
        datetime(2026, 2, 1, tzinfo=UTC),
        datetime(2026, 3, 1, tzinfo=UTC),
        datetime(2026, 4, 1, tzinfo=UTC),
    )


def test_schedule_combines_wti_anchor_with_maintenance_policy() -> None:
    start = datetime(2026, 6, 22, 20, 0, tzinfo=UTC)
    end = datetime(2026, 6, 22, 23, 0, tzinfo=UTC)

    assert expected_opens(WTI, "1h", start, end) == (
        datetime(2026, 6, 22, 20, 30, tzinfo=UTC),
        datetime(2026, 6, 22, 22, 30, tzinfo=UTC),
    )


def test_schedule_groups_missing_opens_into_minimal_sections() -> None:
    timeframe = get_timeframe("1h")
    assert timeframe is not None
    schedule = get_candle_schedule(SPY, timeframe)
    opens = (
        datetime(2026, 6, 22, 13, 30, tzinfo=UTC),
        datetime(2026, 6, 22, 14, 30, tzinfo=UTC),
        datetime(2026, 6, 22, 15, 30, tzinfo=UTC),
    )

    assert schedule.missing_sections(opens, {opens[1]}) == (
        ProviderFetchSection(opens[0], opens[0] + timedelta(hours=1), 1),
        ProviderFetchSection(opens[2], opens[2] + timedelta(hours=1), 1),
    )
