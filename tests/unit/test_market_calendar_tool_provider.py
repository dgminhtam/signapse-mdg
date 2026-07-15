import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import app.providers.market_calendar_tool as provider_module
from app.domain.economic_calendar import EconomicCalendarEnrichmentCandidate
from app.providers.market_calendar_tool import MarketCalendarToolProvider


class FakeSite:
    FOREXFACTORY = "https://www.forexfactory.com/calendar"
    METALSMINE = "metals"
    ENERGYEXCH = "energy"
    CRYPTOCRAFT = "crypto"


async def test_market_calendar_tool_provider_maps_type_and_normalizes_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def scrape_calendar(**kwargs: object) -> object:
        calls.append(kwargs)
        return SimpleNamespace(
            base=[
                {
                    "id": 123,
                    "name": "Non-Farm Employment Change",
                    "currency": "USD",
                    "datetime": datetime(2026, 7, 3, 12, 30, tzinfo=UTC),
                    "impact": "high",
                    "actual": "210K",
                    "forecast": "190K",
                    "previous": "175K",
                    "revision": None,
                    "actual_better_worse": "better",
                    "revision_better_worse": None,
                }
            ],
        )

    fake_cleaner = SimpleNamespace(clean_base=lambda base: base)
    fake_module = SimpleNamespace(
        Site=FakeSite,
        scrape_calendar=scrape_calendar,
    )

    def import_module(name: str) -> object:
        return fake_cleaner if name == "market_calendar_tool.cleaning.cleaner" else fake_module

    monkeypatch.setattr(provider_module.importlib, "import_module", import_module)

    events = await MarketCalendarToolProvider().fetch_events(
        "FOREX",
        datetime(2026, 7, 1, tzinfo=UTC),
        datetime(2026, 7, 8, tzinfo=UTC),
    )

    assert calls == [
        {
            "site": "https://www.forexfactory.com/calendar",
            "date_from": "2026-07-01",
            "date_to": "2026-07-08",
            "extended": False,
        }
    ]
    assert events[0].calendar_type == "FOREX"
    assert events[0].external_event_id == "123"
    assert events[0].actual == "210K"
    assert events[0].actual_better_worse == "better"
    assert events[0].description is None
    assert events[0].news_url is None


async def test_market_calendar_tool_provider_allows_missing_extended_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_to_thread(func: object, *args: object) -> object:
        del func, args
        return SimpleNamespace(
            base=[
                {
                    "id": 123,
                    "name": "Event",
                    "datetime": datetime(2026, 7, 3, 12, 30, tzinfo=UTC),
                }
            ],
            specs=[],
            news=[],
            site_url="https://www.forexfactory.com/calendar",
        )

    monkeypatch.setattr(provider_module.asyncio, "to_thread", fake_to_thread)

    events = await MarketCalendarToolProvider().fetch_events(
        "FOREX",
        datetime(2026, 7, 1, tzinfo=UTC),
        datetime(2026, 7, 8, tzinfo=UTC),
    )

    assert events[0].description is None
    assert events[0].news_url is None


async def test_market_calendar_tool_provider_uses_to_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    async def fake_to_thread(func: object, *args: object) -> object:
        nonlocal called
        del func, args
        called = True
        return SimpleNamespace(base=[])

    monkeypatch.setattr(provider_module.asyncio, "to_thread", fake_to_thread)

    events = await MarketCalendarToolProvider().fetch_events(
        "CRYPTO",
        datetime(2026, 7, 1, tzinfo=UTC),
        datetime(2026, 7, 8, tzinfo=UTC),
    )

    assert called is True
    assert events == []


async def test_market_calendar_tool_provider_fetches_only_selected_details_with_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls: list[str] = []
    active = 0
    max_active = 0

    class FakeResponse:
        def __init__(self, event_id: str) -> None:
            self.event_id = event_id

        async def __aenter__(self) -> FakeResponse:
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0)
            return self

        async def __aexit__(self, *args: object) -> None:
            nonlocal active
            del args
            active -= 1

        def raise_for_status(self) -> None:
            if self.event_id == "3":
                raise RuntimeError("detail failed")

        async def json(self) -> object:
            return {
                "data": {
                    "event_id": self.event_id,
                    "specs": [
                        {
                            "order": 1,
                            "title": "Measures",
                            "html": f"<p>Description {self.event_id}</p>",
                        }
                    ],
                    "linked_threads": {
                        "news": [
                            {
                                "html": (
                                    f'<a href="/news/{self.event_id}-story/hit">Read</a>'
                                )
                            }
                        ]
                    },
                }
            }

    class FakeSession:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs["headers"] == provider_module.DETAIL_HEADERS

        async def __aenter__(self) -> FakeSession:
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        def get(self, url: str) -> FakeResponse:
            urls.append(url)
            return FakeResponse(url.rsplit("-", 1)[-1])

    monkeypatch.setattr(provider_module.aiohttp, "ClientSession", FakeSession)
    candidates = [
        EconomicCalendarEnrichmentCandidate("FOREX", str(event_id))
        for event_id in range(1, 8)
    ]

    results = await MarketCalendarToolProvider().fetch_event_details(candidates)

    assert urls == [
        f"https://www.forexfactory.com/calendar/details/1-{event_id}"
        for event_id in range(1, 8)
    ]
    assert max_active == 5
    assert [result.external_event_id for result in results] == ["1", "2", "4", "5", "6", "7"]
    assert results[0].description == "Description 1"
    assert results[0].news_url == "https://www.forexfactory.com/news/1-story/hit"
