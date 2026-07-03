import asyncio
import importlib
from collections.abc import Iterable, Mapping
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

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
            extended=True,
        )
        clean_base = importlib.import_module("market_calendar_tool.cleaning.cleaner").clean_base
        return SimpleNamespace(
            base=clean_base(result.base),
            specs=getattr(result, "specs", ()),
            news=getattr(result, "news", ()),
            site_url=_site_url(site),
        )


def _normalize_events(
    calendar_type: str,
    scrape_result: object,
) -> list[EconomicCalendarFetchedEvent]:
    base = getattr(scrape_result, "base", scrape_result)
    descriptions = _description_by_id(getattr(scrape_result, "specs", ()))
    news_urls = _news_url_by_id(
        getattr(scrape_result, "news", ()),
        str(getattr(scrape_result, "site_url", "")),
    )
    rows: Iterable[Mapping[str, Any]]
    if hasattr(base, "to_dict"):
        rows = base.to_dict("records")
    elif isinstance(base, Iterable):
        rows = base
    else:
        rows = ()
    events = []
    for row in rows:
        data = dict(row)
        event_id = str(data.get("id"))
        data["description"] = descriptions.get(event_id)
        data["news_url"] = news_urls.get(event_id)
        events.append(_normalize_row(calendar_type, data))
    return events


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
        description=_nullable_string(row.get("description")),
        news_url=_nullable_string(row.get("news_url")),
    )


def _nullable_string(value: object) -> str | None:
    if value is None:
        return None
    if value != value:
        return None
    text = str(value).strip()
    return text or None


def _description_by_id(specs: object) -> dict[str, str]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in _records(specs):
        event_id = _nullable_string(row.get("id"))
        text = _html_text(row.get("html"))
        if event_id and text:
            grouped.setdefault(event_id, []).append({**row, "text": text})

    descriptions: dict[str, str] = {}
    for event_id, event_rows in grouped.items():
        ordered = sorted(event_rows, key=lambda row: _order(row.get("order")))
        measures = next(
            (
                row["text"]
                for row in ordered
                if (_nullable_string(row.get("title")) or "").lower() == "measures"
            ),
            None,
        )
        descriptions[event_id] = measures or ordered[0]["text"]
    return descriptions


def _news_url_by_id(news: object, site_url: str) -> dict[str, str]:
    origin = _origin(site_url)
    urls: dict[str, str] = {}
    for row in _records(news):
        event_id = _nullable_string(row.get("id"))
        if not event_id or event_id in urls:
            continue
        for link in BeautifulSoup(str(row.get("html") or ""), "html.parser").find_all("a"):
            href = _nullable_string(link.get("href"))
            if href and "/news/" in href and href.rstrip("/").endswith("/hit"):
                urls[event_id] = urljoin(origin, href)
                break
    return urls


def _records(value: object) -> list[dict[str, Any]]:
    if hasattr(value, "to_dict"):
        return [dict(row) for row in value.to_dict("records")]
    if isinstance(value, Iterable):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _html_text(value: object) -> str | None:
    return _nullable_string(
        BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)
    )


def _order(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 999_999


def _site_url(site: object) -> str:
    return str(getattr(site, "value", site))


def _origin(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return url
