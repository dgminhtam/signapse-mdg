from datetime import UTC, datetime, timedelta

from app.domain.economic_calendar import (
    EconomicCalendarRepository,
    EconomicCalendarRequest,
    EconomicCalendarResult,
)
from app.domain.errors import EconomicCalendarRequestError

ALLOWED_TYPES = frozenset({"FOREX", "METALS", "ENERGY", "CRYPTO"})
DEFAULT_LIMIT = 1000
MAX_LIMIT = 5000
INVALID_TIME_RANGE_MESSAGE = "The economic calendar time range is invalid."


def parse_economic_calendar_request(
    raw_from: str | None,
    raw_to: str | None,
    raw_types: str | None = None,
    raw_currencies: str | None = None,
    raw_impact: str | None = None,
    raw_limit: str | None = None,
) -> EconomicCalendarRequest:
    start = _parse_utc(raw_from)
    end = _parse_utc(raw_to)
    if start >= end:
        raise EconomicCalendarRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
    types = _parse_csv(raw_types, "INVALID_TYPES", normalize=True)
    invalid_types = sorted(set(types) - ALLOWED_TYPES)
    if invalid_types:
        raise EconomicCalendarRequestError("INVALID_TYPES", "Economic calendar type is invalid.")
    return EconomicCalendarRequest(
        start=start,
        end=end,
        types=types,
        currencies=_parse_csv(raw_currencies, "INVALID_CURRENCIES", normalize=True),
        impact=_parse_csv(raw_impact, "INVALID_IMPACT", normalize=True),
        limit=_parse_limit(raw_limit),
    )


class EconomicCalendarService:
    def __init__(self, repository: EconomicCalendarRepository) -> None:
        self._repository = repository

    async def list_events(self, request: EconomicCalendarRequest) -> EconomicCalendarResult:
        return EconomicCalendarResult(
            start=request.start,
            end=request.end,
            events=await self._repository.list_events(request),
        )


def _parse_utc(raw_value: str | None) -> datetime:
    if raw_value is None:
        raise EconomicCalendarRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
    value = raw_value.strip()
    if not value or not (value.endswith("Z") or value.endswith("+00:00")):
        raise EconomicCalendarRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EconomicCalendarRequestError(
            "INVALID_TIME_RANGE",
            INVALID_TIME_RANGE_MESSAGE,
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise EconomicCalendarRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
    return parsed.astimezone(UTC)


def _parse_csv(raw_value: str | None, code: str, *, normalize: bool) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    values: list[str] = []
    seen: set[str] = set()
    for part in raw_value.split(","):
        value = part.strip()
        if normalize:
            value = value.upper()
        if value and value not in seen:
            values.append(value)
            seen.add(value)
    if not values:
        raise EconomicCalendarRequestError(code, "Economic calendar filter is invalid.")
    return tuple(values)


def _parse_limit(raw_value: str | None) -> int:
    if raw_value is None:
        return DEFAULT_LIMIT
    try:
        limit = int(raw_value.strip())
    except ValueError as exc:
        raise EconomicCalendarRequestError(
            "INVALID_LIMIT",
            "Economic calendar limit is invalid.",
        ) from exc
    if limit < 1 or limit > MAX_LIMIT:
        raise EconomicCalendarRequestError("INVALID_LIMIT", "Economic calendar limit is invalid.")
    return limit
