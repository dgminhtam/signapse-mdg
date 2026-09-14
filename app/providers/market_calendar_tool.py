import asyncio
import importlib
import logging
import time
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger as sdk_logger

from app.core.observability import failure_metadata, log_event
from app.domain.economic_calendar import (
    EconomicCalendarEnrichment,
    EconomicCalendarEnrichmentCandidate,
    EconomicCalendarFetchedEvent,
)
from app.domain.errors import ProviderUnavailableError

SITE_BY_TYPE = {
    "FOREX": "FOREXFACTORY",
    "METALS": "METALSMINE",
    "ENERGY": "ENERGYEXCH",
    "CRYPTO": "CRYPTOCRAFT",
}
UPSTREAM_HOST_BY_TYPE = {
    "FOREX": "www.forexfactory.com",
    "METALS": "www.metalsmine.com",
    "ENERGY": "www.energyexch.com",
    "CRYPTO": "www.cryptocraft.com",
}
SITE_NUMBER_BY_TYPE = {"FOREX": 1, "METALS": 2, "ENERGY": 3, "CRYPTO": 4}
BASE_TIMEOUT_SECONDS = 30
DETAIL_CONCURRENCY = 5
DETAIL_HEADERS = {
    "User-Agent": "market-calendar-tool (+https://github.com/pavelkrusek/market-calendar-tool)",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

logger = logging.getLogger(__name__)
sdk_logger.disable("market_calendar_tool")


class MarketCalendarToolProvider:
    async def fetch_events(
        self,
        calendar_type: str,
        start: datetime,
        end: datetime,
    ) -> list[EconomicCalendarFetchedEvent]:
        if calendar_type not in SITE_BY_TYPE:
            raise ValueError(f"Unsupported economic calendar type: {calendar_type}")
        started = time.perf_counter()
        try:
            result = await asyncio.to_thread(self._scrape, calendar_type, start, end)
            events = _normalize_events(calendar_type, result)
            log_event(
                logger,
                logging.INFO,
                "economic_calendar_fetch_succeeded",
                operation="economic_calendar.fetch_events",
                provider="MARKET_CALENDAR",
                calendar_type=calendar_type,
                upstream_host=UPSTREAM_HOST_BY_TYPE[calendar_type],
                upstream_operation="POST /calendar/apply-settings/1",
                provider_rows=len(events),
                timeout_seconds=BASE_TIMEOUT_SECONDS,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
            )
            return events
        except Exception as exc:
            metadata = failure_metadata(exc)
            metadata.update(
                {
                    "calendar_type": calendar_type,
                    "upstream_host": UPSTREAM_HOST_BY_TYPE[calendar_type],
                    "upstream_operation": "POST /calendar/apply-settings/1",
                    "failure_phase": "base_fetch",
                    "timeout_seconds": BASE_TIMEOUT_SECONDS,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                    "from": start,
                    "to": end,
                }
            )
            raise ProviderUnavailableError(
                "Economic calendar provider is unavailable.",
                failure_reason=str(metadata["failure_reason"]),
                retryable=bool(metadata["retryable"]),
                operation="economic_calendar.fetch_events",
                provider="MARKET_CALENDAR",
                request_from=start,
                request_to=end,
                diagnostic_fields=metadata,
            ) from exc

    async def fetch_event_details(
        self,
        candidates: list[EconomicCalendarEnrichmentCandidate],
    ) -> list[EconomicCalendarEnrichment]:
        if not candidates:
            return []
        started = time.perf_counter()
        semaphore = asyncio.Semaphore(DETAIL_CONCURRENCY)
        async with aiohttp.ClientSession(headers=DETAIL_HEADERS) as session:
            results = await asyncio.gather(
                *(
                    self._fetch_event_detail(session, semaphore, candidate)
                    for candidate in candidates
                )
            )
        enrichments = [result for result, _reason in results if result is not None]
        reasons = Counter(reason for _result, reason in results if reason is not None)
        failed_count = len(candidates) - len(enrichments)
        calendar_types = sorted({candidate.calendar_type for candidate in candidates})
        upstream_hosts = sorted(
            {UPSTREAM_HOST_BY_TYPE[candidate.calendar_type] for candidate in candidates}
        )
        log_event(
            logger,
            logging.WARNING if failed_count else logging.INFO,
            "economic_calendar_enrichment_completed",
            operation="economic_calendar.fetch_event_details",
            provider="MARKET_CALENDAR",
            calendar_type=calendar_types[0] if len(calendar_types) == 1 else None,
            upstream_host=upstream_hosts[0] if len(upstream_hosts) == 1 else None,
            upstream_hosts=upstream_hosts if len(upstream_hosts) > 1 else None,
            upstream_operation="GET /calendar/details/{site_number}-{event_id}",
            attempted_count=len(candidates),
            succeeded_count=len(enrichments),
            failed_count=failed_count,
            connection_failure_count=sum(
                count
                for reason, count in reasons.items()
                if reason in {"CONNECTION_FAILED", "CONNECTION_RESET", "TLS_HANDSHAKE_FAILED"}
            ),
            invalid_event_count=reasons.get("INVALID_UPSTREAM_EVENT", 0),
            failure_reasons=sorted(reasons),
            partial=bool(failed_count),
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
        )
        return enrichments

    def _scrape(self, calendar_type: str, start: datetime, end: datetime) -> object:
        module = importlib.import_module("market_calendar_tool")
        site = getattr(module.Site, SITE_BY_TYPE[calendar_type])
        scraper = importlib.import_module("market_calendar_tool.scraper").BaseScraper(
            site=site,
            date_from=start.date().isoformat(),
            date_to=end.date().isoformat(),
        )
        with scraper.session:
            post = scraper.session.post
            # SDK 0.2.2 hard-codes 10s; override only this scraper's request.
            scraper.session.post = lambda *args, **kwargs: post(*args, **{**kwargs, "timeout": 30})
            result = scraper.scrape()
        clean_base = importlib.import_module("market_calendar_tool.cleaning.cleaner").clean_base
        return SimpleNamespace(
            base=clean_base(result.base),
            site_url=_site_url(site),
        )

    async def _fetch_event_detail(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        candidate: EconomicCalendarEnrichmentCandidate,
    ) -> tuple[EconomicCalendarEnrichment | None, str | None]:
        try:
            async with semaphore:
                async with session.get(_detail_url(candidate)) as response:
                    response.raise_for_status()
                    payload = await response.json()
            return _normalize_detail(candidate, payload), None
        except Exception as exc:
            status = getattr(exc, "status", None)
            reason = (
                "INVALID_UPSTREAM_EVENT"
                if status == 400
                else str(failure_metadata(exc)["failure_reason"])
            )
            return None, reason


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


def _normalize_detail(
    candidate: EconomicCalendarEnrichmentCandidate,
    payload: object,
) -> EconomicCalendarEnrichment:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), Mapping):
        raise ValueError("Economic calendar detail payload is invalid.")
    data = payload["data"]
    event_id = candidate.external_event_id
    specs = [{**row, "id": event_id} for row in _records(data.get("specs", ()))]
    linked_threads = data.get("linked_threads", {})
    news = (
        [{**row, "id": event_id} for row in _records(linked_threads.get("news", ()))]
        if isinstance(linked_threads, Mapping)
        else []
    )
    module = importlib.import_module("market_calendar_tool")
    site = getattr(module.Site, SITE_BY_TYPE[candidate.calendar_type])
    return EconomicCalendarEnrichment(
        calendar_type=candidate.calendar_type,
        external_event_id=event_id,
        description=_description_by_id(specs).get(event_id),
        news_url=_news_url_by_id(news, _site_url(site)).get(event_id),
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
    except TypeError, ValueError:
        return 999_999


def _site_url(site: object) -> str:
    return str(getattr(site, "value", site))


def _origin(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return url


def _detail_url(candidate: EconomicCalendarEnrichmentCandidate) -> str:
    module = importlib.import_module("market_calendar_tool")
    site = getattr(module.Site, SITE_BY_TYPE[candidate.calendar_type])
    return (
        f"{_site_url(site)}/details/"
        f"{SITE_NUMBER_BY_TYPE[candidate.calendar_type]}-{candidate.external_event_id}"
    )
