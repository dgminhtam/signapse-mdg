"""Vantage broker wall clock: New York local time plus seven hours."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
SEVEN_HOURS = timedelta(hours=7)


def to_broker_wall(value: datetime) -> datetime:
    return (value.astimezone(NEW_YORK).replace(tzinfo=None) + SEVEN_HOURS).replace(tzinfo=UTC)


def from_broker_wall(value: datetime, *, nominal: bool = False) -> datetime:
    local = value.replace(tzinfo=None) - SEVEN_HOURS
    first = local.replace(tzinfo=NEW_YORK, fold=0)
    second = local.replace(tzinfo=NEW_YORK, fold=1)
    # Candidate scan buckets can cross a closed DST weekend; actual data stays strict.
    if not nominal and first.utcoffset() != second.utcoffset():
        raise ValueError("Ambiguous or nonexistent broker timestamp at DST transition")
    return first.astimezone(UTC)
