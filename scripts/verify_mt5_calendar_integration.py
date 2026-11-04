"""Exercise the local MT5 -> MDG -> PostgreSQL -> real HTTP/WS path."""

import argparse
import asyncio
import json
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx
import uvicorn
import websockets

from app.core.config import get_settings
from app.db.repositories import PostgresEconomicCalendarRepository
from app.db.session import build_session_factory
from app.domain.errors import ProviderUnavailableError
from app.main import create_app
from scripts.verify_mt5_calendar_poc import gap_summary, week_ranges


async def main(output: Path) -> None:
    settings = get_settings()
    assert settings.database_url and settings.database_url.endswith("/mdg_mt5_local")
    database = build_session_factory(settings)
    assert database is not None
    repository = PostgresEconomicCalendarRepository(database[1])
    app = create_app()
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="warning"))
    serving = asyncio.create_task(server.serve())
    result = {"startedAt": datetime.now(UTC).isoformat(), "weeks": [], "quoteSamples": []}
    quotes = result["quoteSamples"]

    async def observe():
        async with websockets.connect(
            "ws://127.0.0.1:8000/v1/stream?symbols=XAU/USD,EUR/USD"
        ) as ws:
            async for raw in ws:
                item = json.loads(raw)
                if item["type"] == "quote":
                    quotes.append({"at": time.monotonic(), **item})

    observer = None
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=15) as client:
            async with asyncio.timeout(180):
                while True:
                    try:
                        q = await client.get("/v1/quotes", params={"symbols": "XAU/USD"})
                        if q.status_code == 200 and q.json().get("quotes"):
                            break
                    except httpx.TransportError:
                        pass
                    await asyncio.sleep(0.3)
            calendar = app.state.mt5_calendar_provider
            result["openapi"] = (await client.get("/openapi.json")).json()
            windows = week_ranges(datetime.now(UTC).date(), calendar._offset)
            # Confirm that the startup cron persisted native data before manual range checks.
            async with asyncio.timeout(90):
                while True:
                    body = (
                        await client.get(
                            "/v1/economic-calendar",
                            params={"from": windows[1]["from"], "to": windows[1]["to"]},
                        )
                    ).json()
                    statuses = app.state.cronjob_manager.status()
                    if body["events"] and any(s.last_succeeded_at for s in statuses):
                        result["startupCronRunCount"] = statuses[0].run_count
                        result["startupCronFailureCount"] = statuses[0].failure_count
                        break
                    await asyncio.sleep(0.3)
            result["startupCronPersistedCount"] = len(body["events"])
            await app.state.cronjob_manager.stop()
            observer = asyncio.create_task(observe())
            await asyncio.sleep(10)
            result["baselineStart"] = time.monotonic()
            await asyncio.sleep(15)
            result["baselineEnd"] = time.monotonic()
            for window in windows:
                start, end = (datetime.fromisoformat(window[k]) for k in ("from", "to"))
                began = time.monotonic()
                events = await calendar.fetch_events("FOREX", start, end)
                await repository.upsert_events(events)
                response = await client.get(
                    "/v1/economic-calendar",
                    params={"from": window["from"], "to": window["to"], "limit": 5000},
                )
                response.raise_for_status()
                native = [e for e in response.json()["events"] if e["key"].startswith("FOREX:mt5:")]
                assert len(native) == len(events) and len({e["key"] for e in native}) == len(events)
                assert all(e["description"] is None and e["newsUrl"] is None for e in native)
                await repository.upsert_events(events)
                repeated = (
                    await client.get(
                        "/v1/economic-calendar",
                        params={"from": window["from"], "to": window["to"], "limit": 5000},
                    )
                ).json()["events"]
                assert len(repeated) == len(response.json()["events"])
                result["weeks"].append(
                    {
                        "week": window["week"],
                        "count": len(native),
                        "started": began,
                        "ended": time.monotonic(),
                        "events": native,
                    }
                )
                if window["week"] == "previous":
                    legacy = replace(
                        events[0],
                        external_event_id=events[0].external_event_id.removeprefix("mt5:"),
                        description="Local legacy preservation fixture",
                    )
                    await repository.upsert_events([legacy])
                    await repository.upsert_events(events)
                    check = (
                        await client.get(
                            "/v1/economic-calendar",
                            params={"from": window["from"], "to": window["to"], "limit": 5000},
                        )
                    ).json()["events"]
                    assert len(check) == len(native) + 1
                    assert (
                        next(e for e in check if e["key"] == f"FOREX:{legacy.external_event_id}")[
                            "description"
                        ]
                        == legacy.description
                    )
                    result["legacyPreserved"] = True
                print(json.dumps({"week": window["week"], "count": len(native)}), flush=True)
            result["outageStart"] = time.monotonic()
            await calendar.close()
            try:
                await calendar.fetch_events("FOREX", start, end)
            except ProviderUnavailableError:
                result["calendarOutageFails"] = True
            else:
                raise AssertionError("Calendar outage unexpectedly succeeded")
            persisted = await client.get(
                "/v1/economic-calendar",
                params={"from": windows[2]["from"], "to": windows[2]["to"], "limit": 5000},
            )
            assert (
                persisted.status_code == 200
                and len(persisted.json()["events"]) == result["weeks"][2]["count"]
            )
            result["persistedReadDuringOutage"] = True
            result["outageEnd"] = time.monotonic()
            await calendar.start()
            recovered = await calendar.fetch_events("FOREX", start, end)
            assert len(recovered) == result["weeks"][2]["count"]
            result["reconnected"] = True
            await asyncio.sleep(15)
            result["quoteMetrics"] = {}
            for symbol in ("XAU/USD", "EUR/USD"):
                rows = [q for q in quotes if q["symbol"] == symbol]
                assert len({q["receivedAt"] for q in rows}) > 3
                baseline = gap_summary(
                    [q["at"] for q in rows], result["baselineStart"], result["baselineEnd"]
                )
                outage = gap_summary(
                    [q["at"] for q in rows], result["outageStart"], result["outageEnd"]
                )
                result["quoteMetrics"][symbol] = {"baseline": baseline, "calendarOutage": outage}
            result["passed"] = True
    except Exception as exc:
        result["failure"] = f"{type(exc).__name__}: {exc}"
        result["passed"] = False
    finally:
        if observer is not None:
            observer.cancel()
            await asyncio.gather(observer, return_exceptions=True)
        server.should_exit = True
        await asyncio.wait_for(serving, 15)
        result["completedAt"] = datetime.now(UTC).isoformat()
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps({"passed": result["passed"], "failure": result.get("failure")}), flush=True
        )
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(main(parser.parse_args().output))
