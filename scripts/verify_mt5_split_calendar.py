"""Local two-MQL5-Service experiment; reuse the calendar/quote evidence collector."""

import argparse
import asyncio
import json
import time
from datetime import UTC, date, datetime
from pathlib import Path

from scripts.verify_mt5_calendar_poc import Collector, quote_summary, week_ranges


async def run(token_file: Path, output: Path) -> None:
    token = token_file.read_text().strip()
    assert len(token) >= 32
    quotes, calendar = Collector(token), Collector(token)
    servers = []
    result = {"startedAt": datetime.now(UTC).isoformat(), "queries": [], "phases": []}

    async def phase(name, action):
        started = time.monotonic()
        await action
        result["phases"].append(
            {"phase": name, "startedMonotonic": started, "endedMonotonic": time.monotonic()}
        )
        print(json.dumps({"phase": name}), flush=True)

    async def query(window, mode):
        item = await calendar.query(window, mode, 90)
        result["queries"].append(item)
        assert item["validation"]["valid"] and item["events"], item["validation"]

    try:
        for collector, port in ((quotes, 9001), (calendar, 9002)):
            servers.append(
                await asyncio.start_server(collector.accept, "0.0.0.0", port, limit=65536)
            )
        print("Listening on separate quote/calendar sockets", flush=True)
        await asyncio.wait_for(asyncio.gather(quotes.ready.wait(), calendar.ready.wait()), 240)
        assert calendar.hello["role"] == "calendar"
        result["quoteHello"], result["calendarHello"] = quotes.hello, calendar.hello
        windows = week_ranges(date(2026, 11, 4), calendar.calendar_offset)
        await phase("warmup", asyncio.sleep(10))
        await phase("baseline", asyncio.sleep(30))
        for mode in ("first", "warm"):
            for window in windows:
                await phase(f"{mode}_{window['week']}", query(window, mode))
                await asyncio.sleep(1)
        calendar.writer.write(b"POC_DELAY\n")
        await calendar.writer.drain()
        await phase("calendar_thread_blocked_5s", asyncio.sleep(6))
        await phase("after_delay", query(windows[1], "after_delay"))
        calendar.writer.write(b"POC_RECONNECT\n")
        await calendar.writer.drain()

        async def reconnect():
            async with asyncio.timeout(15):
                while calendar.writer is not None:
                    await asyncio.sleep(0.02)
                calendar.ready.clear()
                await calendar.ready.wait()

        await phase("calendar_connection_restart", reconnect())
        result["plannedReconnectErrors"] = list(calendar.errors)
        assert len(calendar.errors) == 1 and "disconnected MT5 frame" in calendar.errors[0]
        calendar.errors.clear()
        await phase("after_reconnect", query(windows[1], "after_reconnect"))
        await phase("recovery", asyncio.sleep(30))
    except Exception as exc:
        result["failure"] = f"{type(exc).__name__}: {exc}"
    finally:
        for server in servers:
            server.close()
        for collector in (quotes, calendar):
            if collector.client_task:
                collector.client_task.cancel()
                await asyncio.gather(collector.client_task, return_exceptions=True)
        for server in servers:
            await server.wait_closed()
        result["quotes"] = quotes.quotes
        result["quoteSummary"] = quote_summary(quotes.quotes, result["phases"])
        result["quoteErrors"], result["calendarErrors"] = quotes.errors, calendar.errors
        result["completedAt"] = datetime.now(UTC).isoformat()
        result["passed"] = (
            "failure" not in result
            and not quotes.errors
            and not calendar.errors
            and len(result["queries"]) == 8
            and all(
                s["advancingTicks"]["observationsInPhase"] > 0
                for p in result["quoteSummary"]
                if p["phase"] in ("baseline", "recovery", "calendar_thread_blocked_5s")
                for s in p["quotes"].values()
            )
        )
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps({"passed": result["passed"], "failure": result.get("failure")}), flush=True
        )
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.token_file, args.output))
