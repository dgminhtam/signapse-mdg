import asyncio
import importlib
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from app.domain.economic_calendar import EconomicCalendarFetchedEvent
from app.domain.errors import ProviderUnavailableError

SITE_BY_TYPE = {
    "FOREX": "FOREXFACTORY",
    "METALS": "METALSMINE",
    "ENERGY": "ENERGYEXCH",
    "CRYPTO": "CRYPTOCRAFT",
}


class MarketCalendarToolProvider:
    async def fetch_events(
        self,
        calendar_type: str,
        start: datetime,
        end: datetime,
    ) -> list[EconomicCalendarFetchedEvent]:
        if calendar_type not in SITE_BY_TYPE:
            raise ValueError(f"Unsupported economic calendar type: {calendar_type}")
        try:
            result = await asyncio.to_thread(self._scrape, calendar_type, start, end)
        except Exception as exc:
            raise ProviderUnavailableError("Economic calendar provider is unavailable.") from exc
        return _normalize_events(calendar_type, result)

    def _scrape(self, calendar_type: str, start: datetime, end: datetime) -> object:
        module = importlib.import_module("market_calendar_tool")
        site = getattr(module.Site, SITE_BY_TYPE[calendar_type])
        result = module.scrape_calendar(
            site=site,
            date_from=start.date().isoformat(),
            date_to=end.date().isoformat(),
            extended=False,
        )
        clean_data = getattr(module, "clean_calendar_data", None) or module.clean_data
        return clean_data(result)


def _normalize_events(
    calendar_type: str,
    scrape_result: object,
) -> list[EconomicCalendarFetchedEvent]:
    base = getattr(scrape_result, "base", scrape_result)
    rows: Iterable[Mapping[str, Any]]
    if hasattr(base, "to_dict"):
        rows = base.to_dict("records")
    elif isinstance(base, Iterable):
        rows = base
    else:
        rows = ()
    return [_normalize_row(calendar_type, dict(row)) for row in rows]


def _normalize_row(calendar_type: str, row: dict[str, Any]) -> EconomicCalendarFetchedEvent:
    scheduled_at = row["datetime"]
    if not isinstance(scheduled_at, datetime):
        scheduled_at = datetime.fromisoformat(str(scheduled_at).replace("Z", "+00:00"))
    return EconomicCalendarFetchedEvent(
        calendar_type=calendar_type,
        external_event_id=str(row["id"]),
        name=str(row["name"]),
        currency=_nullable_string(row.get("currency")),
        impact=_nullable_string(row.get("impact")),
        scheduled_at=scheduled_at,
        actual=_nullable_string(row.get("actual")),
        forecast=_nullable_string(row.get("forecast")),
        previous=_nullable_string(row.get("previous")),
        revision=_nullable_string(row.get("revision")),
        actual_better_worse=_nullable_string(row.get("actual_better_worse")),
        revision_better_worse=_nullable_string(row.get("revision_better_worse")),
    )


def _nullable_string(value: object) -> str | None:
    if value is None:
        return None
    if value != value:
        return None
    text = str(value).strip()
    return text or None
