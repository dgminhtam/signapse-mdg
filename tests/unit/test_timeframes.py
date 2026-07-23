from datetime import UTC, datetime, timedelta

from app.domain.timeframes import (
    candle_close_time,
    expected_candle_count,
    get_timeframe,
    is_aligned,
)


def test_four_hour_timeframe_uses_fixed_utc_contract() -> None:
    timeframe = get_timeframe("4h")
    assert timeframe is not None
    start = datetime(2026, 6, 22, tzinfo=UTC)

    assert timeframe.duration == timedelta(hours=4)
    assert timeframe.provider_interval == "4h"
    assert expected_candle_count(start, start + timedelta(hours=8), timeframe) == 2
    assert candle_close_time(start, timeframe) == start + timedelta(hours=4, milliseconds=-1)
    assert is_aligned(start + timedelta(hours=4), timeframe)
    assert not is_aligned(start + timedelta(hours=2), timeframe)
    assert get_timeframe("h4") is None
