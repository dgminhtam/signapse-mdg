from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import app.providers.market_calendar_tool as provider_module
from app.providers.market_calendar_tool import MarketCalendarToolProvider


class FakeSite:
    FOREXFACTORY = "forex"
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
            ]
        )

    fake_module = SimpleNamespace(
        Site=FakeSite,
        scrape_calendar=scrape_calendar,
        clean_calendar_data=lambda result: result,
    )
    monkeypatch.setattr(provider_module.importlib, "import_module", lambda name: fake_module)

    events = await MarketCalendarToolProvider().fetch_events(
        "FOREX",
        datetime(2026, 7, 1, tzinfo=UTC),
        datetime(2026, 7, 8, tzinfo=UTC),
    )

    assert calls == [
        {
            "site": "forex",
            "date_from": "2026-07-01",
            "date_to": "2026-07-08",
            "extended": False,
        }
    ]
    assert events[0].calendar_type == "FOREX"
    assert events[0].external_event_id == "123"
    assert events[0].actual == "210K"
    assert events[0].actual_better_worse == "better"


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
