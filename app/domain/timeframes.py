from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class Timeframe:
    value: str
    duration: timedelta
    provider_interval: str


TIMEFRAMES = {
    value: Timeframe(value=value, duration=timedelta(minutes=minutes), provider_interval=value)
    for value, minutes in (
        ("1m", 1),
        ("5m", 5),
        ("15m", 15),
        ("1h", 60),
        ("1d", 1440),
    )
}

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def get_timeframe(value: str) -> Timeframe | None:
    return TIMEFRAMES.get(value)


def is_aligned(value: datetime, timeframe: Timeframe) -> bool:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        return False
    elapsed = value.astimezone(UTC) - EPOCH
    return elapsed % timeframe.duration == timedelta(0)


def expected_candle_count(
    start: datetime,
    end: datetime,
    timeframe: Timeframe,
) -> int:
    return int((end - start) / timeframe.duration)
