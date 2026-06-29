from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class Timeframe:
    value: str
    duration: timedelta
    provider_interval: str
    calendar_month: bool = False


TIMEFRAMES = {
    value: Timeframe(value=value, duration=timedelta(minutes=minutes), provider_interval=value)
    for value, minutes in (
        ("1m", 1),
        ("5m", 5),
        ("15m", 15),
        ("30m", 30),
        ("1h", 60),
        ("1d", 1440),
        ("1w", 10080),
    )
}
TIMEFRAMES["1mo"] = Timeframe(
    value="1mo",
    duration=timedelta(days=31),
    provider_interval="1mo",
    calendar_month=True,
)

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
MILLISECONDS = timedelta(milliseconds=1)


def get_timeframe(value: str) -> Timeframe | None:
    return TIMEFRAMES.get(value)


def is_aligned(value: datetime, timeframe: Timeframe) -> bool:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        return False
    if timeframe.calendar_month:
        utc_value = value.astimezone(UTC)
        return (
            utc_value.day == 1
            and utc_value.hour == 0
            and utc_value.minute == 0
            and utc_value.second == 0
            and utc_value.microsecond == 0
        )
    elapsed = value.astimezone(UTC) - EPOCH
    return elapsed % timeframe.duration == timedelta(0)


def expected_candle_count(
    start: datetime,
    end: datetime,
    timeframe: Timeframe,
) -> int:
    if timeframe.calendar_month:
        return len(month_opens(start, end))
    return int((end - start) / timeframe.duration)


def candle_close_time(open_time: datetime, timeframe: Timeframe) -> datetime:
    if timeframe.calendar_month:
        return add_month(open_time.astimezone(UTC)) - MILLISECONDS
    return open_time + timeframe.duration - MILLISECONDS


def last_open_before(end: datetime, timeframe: Timeframe) -> datetime:
    if not timeframe.calendar_month:
        return end - timeframe.duration
    month_start = _month_start(end)
    return add_month(month_start, -1) if month_start >= end else month_start


def month_opens(start: datetime, end: datetime) -> tuple[datetime, ...]:
    cursor = _month_start(start)
    if cursor < start:
        cursor = add_month(cursor)
    opens: list[datetime] = []
    while cursor < end:
        opens.append(cursor)
        cursor = add_month(cursor)
    return tuple(opens)


def add_month(value: datetime, months: int = 1) -> datetime:
    month_index = value.year * 12 + value.month - 1 + months
    year = month_index // 12
    month = month_index % 12 + 1
    return value.replace(year=year, month=month, day=min(value.day, monthrange(year, month)[1]))


def _month_start(value: datetime) -> datetime:
    utc_value = value.astimezone(UTC)
    return datetime(utc_value.year, utc_value.month, 1, tzinfo=UTC)
