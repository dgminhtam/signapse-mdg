from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routes_economic_calendar import get_economic_calendar_service
from app.domain.economic_calendar import (
    EconomicCalendarEvent,
    EconomicCalendarRequest,
    EconomicCalendarResult,
)
from app.domain.errors import DatabaseUnavailableError
from app.main import app

START = datetime(2026, 7, 1, tzinfo=UTC)


class StubEconomicCalendarService:
    def __init__(
        self,
        result: EconomicCalendarResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or EconomicCalendarResult(START, datetime(2026, 7, 8, tzinfo=UTC), [])
        self.error = error
        self.requested: EconomicCalendarRequest | None = None

    async def list_events(self, request: EconomicCalendarRequest) -> EconomicCalendarResult:
        self.requested = request
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


def valid_params() -> dict[str, str]:
    return {
        "from": "2026-07-01T00:00:00Z",
        "to": "2026-07-08T00:00:00Z",
    }


async def test_economic_calendar_serializes_public_contract(client: AsyncClient) -> None:
    event = EconomicCalendarEvent(
        calendar_type="FOREX",
        external_event_id="123456",
        name="Non-Farm Employment Change",
        currency="USD",
        impact="HIGH",
        scheduled_at=datetime(2026, 7, 3, 12, 30, tzinfo=UTC),
        actual="210K",
        forecast="190K",
        previous="175K",
        revision=None,
        actual_better_worse="better",
        revision_better_worse=None,
        description="Change in the number of employed people.",
        news_url="https://www.forexfactory.com/news/123456-nfp-preview/hit",
        first_seen_at=START,
        last_seen_at=datetime(2026, 7, 3, 12, 31, tzinfo=UTC),
        last_changed_at=datetime(2026, 7, 3, 12, 31, tzinfo=UTC),
    )
    app.dependency_overrides[get_economic_calendar_service] = lambda: StubEconomicCalendarService(
        EconomicCalendarResult(START, datetime(2026, 7, 8, tzinfo=UTC), [event])
    )

    response = await client.get("/v1/economic-calendar", params=valid_params())

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"from", "to", "events"}
    assert payload["events"][0] == {
        "key": "FOREX:123456",
        "type": "FOREX",
        "name": "Non-Farm Employment Change",
        "currency": "USD",
        "impact": "HIGH",
        "scheduledAt": "2026-07-03T12:30:00Z",
        "actual": "210K",
        "forecast": "190K",
        "previous": "175K",
        "revision": None,
        "actualBetterWorse": "better",
        "revisionBetterWorse": None,
        "description": "Change in the number of employed people.",
        "newsUrl": "https://www.forexfactory.com/news/123456-nfp-preview/hit",
        "firstSeenAt": "2026-07-01T00:00:00Z",
        "lastSeenAt": "2026-07-03T12:31:00Z",
        "lastChangedAt": "2026-07-03T12:31:00Z",
    }
    assert "externalEventId" not in response.text
    assert '"id"' not in response.text
    assert "history" not in response.text


async def test_economic_calendar_passes_normalized_filters(client: AsyncClient) -> None:
    service = StubEconomicCalendarService()
    app.dependency_overrides[get_economic_calendar_service] = lambda: service

    response = await client.get(
        "/v1/economic-calendar",
        params={
            **valid_params(),
            "types": "forex,METALS",
            "currencies": "usd,XAU",
            "impact": "high",
            "limit": "2",
        },
    )

    assert response.status_code == 200
    assert service.requested is not None
    assert service.requested.types == ("FOREX", "METALS")
    assert service.requested.currencies == ("USD", "XAU")
    assert service.requested.impact == ("HIGH",)
    assert service.requested.limit == 2


async def test_economic_calendar_returns_empty_events(client: AsyncClient) -> None:
    app.dependency_overrides[get_economic_calendar_service] = lambda: StubEconomicCalendarService()

    response = await client.get("/v1/economic-calendar", params=valid_params())

    assert response.status_code == 200
    assert response.json()["events"] == []


@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({}, "INVALID_TIME_RANGE"),
        ({"from": "2026-07-01T00:00:00Z", "to": "bad"}, "INVALID_TIME_RANGE"),
        ({**valid_params(), "types": "UNKNOWN"}, "INVALID_TYPES"),
        ({**valid_params(), "currencies": " , "}, "INVALID_CURRENCIES"),
        ({**valid_params(), "impact": " , "}, "INVALID_IMPACT"),
        ({**valid_params(), "limit": "5001"}, "INVALID_LIMIT"),
    ],
)
async def test_economic_calendar_returns_contract_400(
    client: AsyncClient,
    params: dict[str, str],
    code: str,
) -> None:
    app.dependency_overrides[get_economic_calendar_service] = lambda: StubEconomicCalendarService()

    response = await client.get("/v1/economic-calendar", params=params)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == code


async def test_economic_calendar_sanitizes_database_failure(client: AsyncClient) -> None:
    app.dependency_overrides[get_economic_calendar_service] = lambda: StubEconomicCalendarService(
        error=DatabaseUnavailableError("postgresql://secret")
    )

    response = await client.get("/v1/economic-calendar", params=valid_params())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "secret" not in response.text
