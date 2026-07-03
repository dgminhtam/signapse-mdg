from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import app.providers.market_calendar_tool as provider_module
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
            specs=[
                {"id": 123, "order": 2, "title": "Source", "html": "<p>Ignored</p>"},
                {"id": 123, "order": 3, "title": "Measures", "html": "<p>Jobs added</p>"},
            ],
            news=[
                {
                    "id": 123,
                    "html": '<a href="/news/123-nfp-preview/hit">Read</a>',
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
            "extended": True,
        }
    ]
    assert events[0].calendar_type == "FOREX"
    assert events[0].external_event_id == "123"
    assert events[0].actual == "210K"
    assert events[0].actual_better_worse == "better"
    assert events[0].description == "Jobs added"
    assert events[0].news_url == "https://www.forexfactory.com/news/123-nfp-preview/hit"


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
