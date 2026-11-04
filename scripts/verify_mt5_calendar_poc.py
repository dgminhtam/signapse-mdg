"""Read three calendar weeks on the local MT5 Service and measure shared-loop quote gaps."""

import argparse
import asyncio
import hmac
import json
import math
import time
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, DecimalException
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domain.mt5_time import from_broker_wall, to_broker_wall

VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")
FRAME_LIMIT = 65536
WATCHED_SYMBOLS = ("XAUUSD", "EURUSD")
NUMERIC_FIELDS = {
    "actualRaw": "actual",
    "forecastRaw": "forecast",
    "previousRaw": "previous",
    "revisedPreviousRaw": "revisedPrevious",
}


def week_ranges(anchor: date, calendar_offset: int | None = None) -> list[dict[str, Any]]:
    monday = anchor - timedelta(days=anchor.weekday())
    result = []
    for offset, label in ((-1, "previous"), (0, "current"), (1, "next")):
        start = datetime.combine(monday + timedelta(weeks=offset), datetime.min.time(), VIETNAM)
        end = start + timedelta(days=7)
        result.append(
            {
                "week": label,
                "from": start.astimezone(UTC).isoformat(),
                "to": end.astimezone(UTC).isoformat(),
                "fromRaw": (
                    int(to_broker_wall(start).timestamp())
                    if calendar_offset is None
                    else int(start.timestamp()) + calendar_offset
                ),
                "toRaw": (
                    int(to_broker_wall(end).timestamp())
                    if calendar_offset is None
                    else int(end.timestamp()) + calendar_offset
                ),
            }
        )
    return result


def native_decimal(value: object) -> str | None:
    if value is None or value == "-9223372036854775808":
        return None
    if not isinstance(value, str):
        raise ValueError("Calendar raw numeric value must be a string or null")
    return format(Decimal(int(value)) / Decimal(1_000_000), "f")


def calendar_offset_seconds(hello: dict[str, Any]) -> int:
    if type(hello.get("serverTime")) is not int or type(hello.get("utcTime")) is not int:
        raise ValueError("Invalid calendar session clocks")
    difference = hello["serverTime"] - hello["utcTime"]
    offset = round(difference / 3600) * 3600
    if offset not in (7200, 10800) or abs(difference - offset) > 2:
        raise ValueError("Calendar session offset does not match Vantage clock")
    return offset


def normalize_event(message: dict[str, Any], calendar_offset: int | None = None) -> dict[str, Any]:
    result = {key: value for key, value in message.items() if key not in ("type", "id")}
    for field in ("valueId", "eventId"):
        if not isinstance(result.get(field), str) or not result[field].isdigit():
            raise ValueError("Invalid calendar identity")
    if type(result.get("timeRaw")) is not int:
        raise ValueError("Invalid calendar event timestamp")
    try:
        result["barProfileScheduledAt"] = from_broker_wall(
            datetime.fromtimestamp(result["timeRaw"], UTC)
        ).isoformat()
    except ValueError as exc:
        result["barProfileScheduledAt"] = None
        result["barProfileConversionError"] = str(exc)
    if calendar_offset is None:
        result["scheduledAt"] = result["barProfileScheduledAt"]
        if result["scheduledAt"] is None:
            result["utcConversionError"] = result["barProfileConversionError"]
    else:
        # shortcut: session-offset calendar time verified for this PoC; recheck at DST changes.
        result["scheduledAt"] = datetime.fromtimestamp(
            result["timeRaw"] - calendar_offset, UTC
        ).isoformat()
    for raw_name, name in NUMERIC_FIELDS.items():
        result[name] = native_decimal(result.get(raw_name))
    # Unit/multiplier remain explicit: these are native indicator numbers, not MDG display strings.
    return result


def gap_summary(times: list[float], start: float, end: float) -> dict[str, Any]:
    """Include gaps crossing both phase boundaries, even when no tick arrives in the phase."""
    contained = sorted(
        (right - left) * 1000
        for left, right in zip(times, times[1:], strict=False)
        if start <= left and right <= end
    )
    gaps = [
        (right - left) * 1000
        for left, right in zip(times, times[1:], strict=False)
        if left < end and right > start
    ]
    gaps.sort()
    return {
        "observationsInPhase": sum(start <= item <= end for item in times),
        "maxGapMs": round(max(gaps), 3) if gaps else None,
        "p95GapMs": round(gaps[math.ceil(len(gaps) * 0.95) - 1], 3) if gaps else None,
        "gapCountIncludingBoundaries": len(gaps),
        "fullyContainedMaxGapMs": round(max(contained), 3) if contained else None,
        "fullyContainedP95GapMs": (
            round(contained[math.ceil(len(contained) * 0.95) - 1], 3) if contained else None
        ),
        "fullyContainedGapCount": len(contained),
    }


class Collector:
    def __init__(self, token: str) -> None:
        self.token = token
        self.ready = asyncio.Event()
        self.writer: asyncio.StreamWriter | None = None
        self.client_task: asyncio.Task[Any] | None = None
        self.hello: dict[str, Any] | None = None
        self.calendar_offset: int | None = None
        self.quotes: list[dict[str, Any]] = []
        self.status: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self.sequence = 0
        self.last_raw: dict[str, int] = {}
        self.pending: dict[str, Any] | None = None
        self.future: asyncio.Future[dict[str, Any]] | None = None

    @staticmethod
    async def line(reader: asyncio.StreamReader) -> bytes:
        line = await asyncio.wait_for(reader.readline(), 120)
        if not line or len(line) > FRAME_LIMIT or not line.endswith(b"\n"):
            raise ValueError("Invalid or disconnected MT5 frame")
        return line.rstrip(b"\r\n")

    async def accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        owned = False
        try:
            first = await asyncio.wait_for(self.line(reader), 5)
            if not hmac.compare_digest(first, f"HELLO {self.token}".encode()) or self.writer:
                raise ValueError("MT5 authentication or single-client check failed")
            hello = json.loads(await asyncio.wait_for(self.line(reader), 5))
            if (
                hello.get("type") != "hello"
                or hello.get("version") != 1
                or hello.get("server") != "VantageMarkets-Demo"
                or hello.get("service") is not True
                or hello.get("algoTrading") is not False
                or not set(WATCHED_SYMBOLS).issubset(set(hello.get("symbols", [])))
            ):
                raise ValueError("MT5 handshake mismatch")
            now = datetime.now(UTC)
            for clock in (
                from_broker_wall(datetime.fromtimestamp(hello["serverTime"], UTC)),
                datetime.fromtimestamp(hello["utcTime"], UTC),
            ):
                if abs((now - clock).total_seconds()) > 15:
                    raise ValueError("MT5 clock mismatch")
            self.hello = hello
            self.calendar_offset = calendar_offset_seconds(hello)
            self.writer = writer
            self.client_task = asyncio.current_task()
            owned = True
            self.ready.set()
            print(json.dumps({"phase": "connected", "symbols": len(hello["symbols"])}), flush=True)
            while True:
                row = json.loads(await self.line(reader))
                received = time.monotonic()
                kind = row.get("type")
                if kind == "tick":
                    self.tick(row, received)
                elif kind == "status" and type(row.get("connected")) is bool:
                    self.status.append({"atMonotonic": received, "connected": row["connected"]})
                elif kind in ("calendar_begin", "calendar_event", "calendar_error", "calendar_end"):
                    self.calendar(row, received)
                else:
                    raise ValueError("Unknown MT5 message kind")
        except asyncio.CancelledError:
            raise
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            TimeoutError,
            OverflowError,
            DecimalException,
        ) as exc:
            self.errors.append(f"{type(exc).__name__}: {exc}")
            if self.future is not None and not self.future.done():
                self.future.set_exception(ValueError("MT5 connection ended during calendar query"))
        finally:
            if owned:
                self.writer = None
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    def tick(self, row: dict[str, Any], received: float) -> None:
        if type(row.get("seq")) is not int or row["seq"] <= self.sequence:
            raise ValueError("MT5 quote sequence did not advance")
        self.sequence = row["seq"]
        if row.get("symbol") not in WATCHED_SYMBOLS:
            return
        if row.get("connected") is not True or type(row.get("timeMscRaw")) is not int:
            raise ValueError("Invalid MT5 quote status or timestamp")
        for field in ("bid", "ask"):
            if not Decimal(row[field]).is_finite() or Decimal(row[field]) <= 0:
                raise ValueError("Invalid MT5 quote price")
        raw = row["timeMscRaw"]
        symbol = row["symbol"]
        previous = self.last_raw.get(symbol)
        if previous is not None and raw < previous:
            raise ValueError("MT5 quote source timestamp went backwards")
        timestamp = from_broker_wall(datetime.fromtimestamp(raw / 1000, UTC))
        age = (datetime.now(UTC) - timestamp).total_seconds() * 1000
        if age < -5000:
            raise ValueError("MT5 quote source timestamp is in the future")
        self.quotes.append(
            {
                "symbol": symbol,
                "atMonotonic": received,
                "receivedAt": datetime.now(UTC).isoformat(),
                "timeMscRaw": raw,
                "sourceAt": timestamp.isoformat(),
                "ageMs": round(age, 3),
                "advancing": previous is None or raw > previous,
                "bid": row["bid"],
                "ask": row["ask"],
            }
        )
        self.last_raw[symbol] = raw

    def calendar(self, row: dict[str, Any], received: float) -> None:
        if self.pending is None or row.get("id") != self.pending["id"]:
            raise ValueError("Unexpected calendar correlation ID")
        kind = row["type"]
        if kind == "calendar_begin":
            if "begin" in self.pending:
                raise ValueError("Duplicate calendar begin")
            self.pending["begin"] = row
        elif kind == "calendar_event":
            self.pending["events"].append(normalize_event(row, self.calendar_offset))
        elif kind == "calendar_error":
            self.pending["metadataErrors"].append(row)
        else:
            self.pending["end"] = row
            self.pending["endedMonotonic"] = received
            if self.future is not None and not self.future.done():
                self.future.set_result(self.pending)

    async def query(self, window: dict[str, Any], mode: str, timeout: float) -> dict[str, Any]:
        if self.writer is None:
            raise ValueError("No MT5 connection")
        self.pending = {
            **window,
            "mode": mode,
            "id": uuid4().hex,
            "startedAt": datetime.now(UTC).isoformat(),
            "startedMonotonic": time.monotonic(),
            "events": [],
            "metadataErrors": [],
        }
        self.future = asyncio.get_running_loop().create_future()
        self.writer.write(
            f"CALENDAR\t{self.pending['id']}\t{window['fromRaw']}\t{window['toRaw']}\tALL\n".encode()
        )
        await self.writer.drain()
        try:
            result = await asyncio.wait_for(self.future, timeout)
        except (ValueError, TimeoutError) as exc:
            result = self.pending
            result["failure"] = type(exc).__name__
            result["endedMonotonic"] = time.monotonic()
        result["validation"] = validate_query(result)
        print(
            json.dumps(
                {
                    "phase": f"{mode}_{window['week']}",
                    "events": len(result["events"]),
                    "fetchMs": result.get("begin", {}).get("fetchMs"),
                    "totalMs": result.get("end", {}).get("totalMs"),
                    "error": result.get("end", {}).get("error"),
                    "valid": result["validation"]["valid"],
                }
            ),
            flush=True,
        )
        self.pending = None
        self.future = None
        return result


def validate_query(query: dict[str, Any]) -> dict[str, Any]:
    events = query["events"]
    start, end = datetime.fromisoformat(query["from"]), datetime.fromisoformat(query["to"])
    errors = []
    if query.get("failure"):
        errors.append(query["failure"])
    begin, finish = query.get("begin", {}), query.get("end", {})
    if begin.get("error") != 0 or finish.get("error") != 0:
        errors.append("native_error_or_incomplete")
    expected = begin.get("nativeCount", -1) - finish.get("outOfRangeCount", 0)
    if expected != len(events) or finish.get("count") != len(events):
        errors.append("row_count_mismatch")
    if len({event["valueId"] for event in events}) != len(events):
        errors.append("duplicate_occurrence_id")
    if any(event["scheduledAt"] is None for event in events):
        errors.append("ambiguous_or_nonexistent_broker_time")
    if any(
        event["scheduledAt"] is not None
        and not start <= datetime.fromisoformat(event["scheduledAt"]) < end
        for event in events
    ):
        errors.append("outside_utc_window")
    if query["metadataErrors"]:
        errors.append("metadata_error")
    return {
        "valid": not errors,
        "errors": errors,
        "count": len(events),
        "currencies": dict(sorted(Counter(event.get("currency") for event in events).items())),
        "actualCount": sum(event["actual"] is not None for event in events),
        "forecastCount": sum(event["forecast"] is not None for event in events),
        "revisedPreviousCount": sum(event["revisedPrevious"] is not None for event in events),
    }


def quote_summary(
    quotes: list[dict[str, Any]], phases: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result = []
    for phase in phases:
        start, end = phase["startedMonotonic"], phase["endedMonotonic"]
        per_symbol = {}
        for symbol in WATCHED_SYMBOLS:
            rows = [quote for quote in quotes if quote["symbol"] == symbol]
            inside = [quote for quote in rows if start <= quote["atMonotonic"] <= end]
            before_end = [quote for quote in rows if quote["atMonotonic"] <= end]
            per_symbol[symbol] = {
                "snapshots": gap_summary([q["atMonotonic"] for q in rows], start, end),
                "advancingTicks": gap_summary(
                    [q["atMonotonic"] for q in rows if q["advancing"]], start, end
                ),
                "maxReceivedAgeMs": max((q["ageMs"] for q in inside), default=None),
                "sourceAgeAtPhaseEndMs": (
                    round(
                        before_end[-1]["ageMs"] + (end - before_end[-1]["atMonotonic"]) * 1000,
                        3,
                    )
                    if before_end
                    else None
                ),
            }
        result.append(
            {
                "phase": phase["phase"],
                "durationMs": round((end - start) * 1000, 3),
                "quotes": per_symbol,
            }
        )
    return result


async def run(args: argparse.Namespace) -> None:
    token = args.token_file.read_text().strip()
    if len(token) < 32:
        raise ValueError("Private token is missing or too short")
    collector = Collector(token)
    result: dict[str, Any] = {
        "at": datetime.now(UTC).isoformat(),
        "anchorDate": args.anchor_date.isoformat(),
        "scope": "local isolated native MQL5 shared-loop PoC; no MDG database writes",
        "weeks": week_ranges(args.anchor_date),
        "queries": [],
        "phases": [],
    }
    server = await asyncio.start_server(collector.accept, args.host, args.port, limit=FRAME_LIMIT)
    print(json.dumps({"phase": "listening", "port": args.port}), flush=True)
    try:
        await asyncio.wait_for(collector.ready.wait(), args.connect_timeout)
        result["hello"] = collector.hello
        result["calendarOffsetSeconds"] = collector.calendar_offset
        result["calendarTimestampInterpretation"] = (
            "Native calendar uses the validated session offset for all queried weeks; "
            "barProfileScheduledAt preserves the separate historical bar-clock interpretation"
        )
        result["weeks"] = week_ranges(args.anchor_date, collector.calendar_offset)
        for mode in ("cold", "warm"):
            phase_name = "baseline" if mode == "cold" else "between_passes"
            started = time.monotonic()
            await asyncio.sleep(args.baseline_seconds if mode == "cold" else 5)
            result["phases"].append(
                {
                    "phase": phase_name,
                    "startedMonotonic": started,
                    "endedMonotonic": time.monotonic(),
                }
            )
            print(json.dumps({"phase": phase_name, "quotes": len(collector.quotes)}), flush=True)
            for window in result["weeks"]:
                query = await collector.query(window, mode, args.query_timeout)
                result["queries"].append(query)
                result["phases"].append(
                    {
                        "phase": f"{mode}_{window['week']}",
                        "startedMonotonic": query["startedMonotonic"],
                        "endedMonotonic": query["endedMonotonic"],
                    }
                )
                if query.get("failure"):
                    raise ValueError("Calendar transport did not complete; see partial evidence")
                await asyncio.sleep(1)
        started = time.monotonic()
        await asyncio.sleep(args.recovery_seconds)
        result["phases"].append(
            {
                "phase": "recovery",
                "startedMonotonic": started,
                "endedMonotonic": time.monotonic(),
            }
        )
    except (OSError, ValueError, TimeoutError) as exc:
        result["failure"] = f"{type(exc).__name__}: {exc}"
    finally:
        server.close()
        if collector.client_task is not None:
            collector.client_task.cancel()
            await asyncio.gather(collector.client_task, return_exceptions=True)
        await server.wait_closed()
        result["quotes"] = collector.quotes
        result["brokerStatus"] = collector.status
        result["connectionErrors"] = collector.errors
        result["quoteSummary"] = quote_summary(collector.quotes, result["phases"])
        result["completedAt"] = datetime.now(UTC).isoformat()
        result["passed"] = (
            "failure" not in result
            and not collector.errors
            and len(result["queries"]) == 6
            and all(q["validation"]["valid"] and q["events"] for q in result["queries"])
            and all(
                symbol["advancingTicks"]["observationsInPhase"] > 0
                for phase in result["quoteSummary"]
                if phase["phase"] in ("baseline", "recovery")
                for symbol in phase["quotes"].values()
            )
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({"phase": "finished", "passed": result["passed"]}), flush=True)
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument(
        "--anchor-date", type=date.fromisoformat, default=datetime.now(VIETNAM).date()
    )
    parser.add_argument("--baseline-seconds", type=float, default=30)
    parser.add_argument("--recovery-seconds", type=float, default=30)
    parser.add_argument("--query-timeout", type=float, default=90)
    parser.add_argument("--connect-timeout", type=float, default=240)
    asyncio.run(run(parser.parse_args()))
