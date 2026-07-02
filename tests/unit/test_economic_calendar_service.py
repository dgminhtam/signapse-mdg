from datetime import UTC, datetime

import pytest

from app.domain.economic_calendar import EconomicCalendarRequest
from app.domain.errors import EconomicCalendarRequestError
from app.services.economic_calendar import parse_economic_calendar_request


class FakeRepository:
    def __init__(self) -> None:
        self.requests: list[EconomicCalendarRequest] = []

    async def list_events(self, request: EconomicCalendarRequest) -> list[object]:
        self.requests.append(request)
        return []


def test_parse_economic_calendar_request_normalizes_filters() -> None:
    request = parse_economic_calendar_request(
        "2026-07-01T00:00:00Z",
        "2026-07-08T00:00:00Z",
        " forex, METALS,forex ",
        " usd, XAU,usd ",
        " high,MEDIUM,high ",
        "25",
    )

    assert request.start == datetime(2026, 7, 1, tzinfo=UTC)
    assert request.end == datetime(2026, 7, 8, tzinfo=UTC)
    assert request.types == ("FOREX", "METALS")
    assert request.currencies == ("USD", "XAU")
    assert request.impact == ("HIGH", "MEDIUM")
    assert request.limit == 25


@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({"raw_from": None}, "INVALID_TIME_RANGE"),
        ({"raw_from": "2026-07-01T00:00:00+07:00"}, "INVALID_TIME_RANGE"),
        ({"raw_to": "2026-07-01T00:00:00Z"}, "INVALID_TIME_RANGE"),
        ({"raw_types": "FOREX,UNKNOWN"}, "INVALID_TYPES"),
        ({"raw_currencies": " , "}, "INVALID_CURRENCIES"),
        ({"raw_impact": " , "}, "INVALID_IMPACT"),
        ({"raw_limit": "0"}, "INVALID_LIMIT"),
        ({"raw_limit": "bad"}, "INVALID_LIMIT"),
    ],
)
def test_parse_economic_calendar_request_rejects_invalid_values(
    params: dict[str, str | None],
    code: str,
) -> None:
    values = {
        "raw_from": "2026-07-01T00:00:00Z",
        "raw_to": "2026-07-08T00:00:00Z",
        "raw_types": None,
        "raw_currencies": None,
        "raw_impact": None,
        "raw_limit": None,
    }
    values.update(params)

    with pytest.raises(EconomicCalendarRequestError) as error:
        parse_economic_calendar_request(**values)

    assert error.value.code == code


async def test_service_returns_empty_list_without_provider_fallback() -> None:
    from app.services.economic_calendar import EconomicCalendarService

    repository = FakeRepository()
    request = parse_economic_calendar_request(
        "2026-07-01T00:00:00Z",
        "2026-07-08T00:00:00Z",
    )

    result = await EconomicCalendarService(repository).list_events(request)  # type: ignore[arg-type]

    assert result.events == []
    assert repository.requests == [request]
