import argparse
import asyncio
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from app.domain.mt5_time import from_broker_wall, to_broker_wall
from scripts import verify_mt5_calendar_poc as poc
from scripts.verify_mt5_calendar_poc import (
    calendar_offset_seconds,
    gap_summary,
    native_decimal,
    normalize_event,
    week_ranges,
)


def test_three_weeks_keep_vietnam_midnight_across_vantage_dst_change() -> None:
    windows = week_ranges(date(2026, 11, 4))
    assert [window["week"] for window in windows] == ["previous", "current", "next"]
    assert windows[0]["from"] == "2026-10-25T17:00:00+00:00"
    assert windows[0]["to"] == "2026-11-01T17:00:00+00:00"
    assert windows[0]["toRaw"] - windows[0]["fromRaw"] == 7 * 86400 - 3600
    for window in windows:
        for key, raw in (("from", "fromRaw"), ("to", "toRaw")):
            assert (
                from_broker_wall(datetime.fromtimestamp(window[raw], UTC)).isoformat()
                == window[key]
            )


def test_native_value_preserves_zero_negative_and_missing_without_float() -> None:
    assert native_decimal(None) is None
    assert native_decimal("-9223372036854775808") is None
    assert native_decimal("0") == "0"
    assert native_decimal("-1234567") == "-1.234567"
    assert native_decimal("9007199254740993") == "9007199254.740993"
    with pytest.raises(ValueError):
        native_decimal(0)


def test_query_without_ticks_still_measures_gap_crossing_both_boundaries() -> None:
    result = gap_summary([0.0, 0.25, 10.5, 10.75], 1.0, 10.0)
    assert result["observationsInPhase"] == 0
    assert result["maxGapMs"] == 10250
    assert result["p95GapMs"] == 10250
    assert result["gapCountIncludingBoundaries"] == 1
    assert result["fullyContainedMaxGapMs"] is None
    assert result["fullyContainedP95GapMs"] is None
    assert result["fullyContainedGapCount"] == 0


def test_baseline_internal_control_excludes_the_following_query_gap() -> None:
    result = gap_summary([0.0, 0.25, 0.45, 3.8], 0.0, 0.5)
    assert result["maxGapMs"] == 3350
    assert result["fullyContainedMaxGapMs"] == 250
    assert result["fullyContainedP95GapMs"] == 250
    assert result["fullyContainedGapCount"] == 2


def test_ambiguous_dst_calendar_row_is_retained_without_inventing_utc() -> None:
    event = normalize_event(
        {
            "valueId": "123",
            "eventId": "456",
            "timeRaw": int(datetime(2026, 11, 1, 8, 30, tzinfo=UTC).timestamp()),
            "actualRaw": "1200000",
            "unit": 1,
            "multiplier": 2,
        }
    )
    assert event["timeRaw"] == 1793521800
    assert event["scheduledAt"] is None
    assert "Ambiguous" in event["utcConversionError"]
    assert event["actual"] == "1.2"
    assert event["multiplier"] == 2


def test_calendar_history_uses_session_offset_without_changing_bar_profile() -> None:
    previous = normalize_event({"valueId": "123", "eventId": "456", "timeRaw": 1793284200}, 7200)
    assert previous["scheduledAt"] == "2026-10-29T12:30:00+00:00"
    assert previous["barProfileScheduledAt"] == "2026-10-29T11:30:00+00:00"
    current = normalize_event(
        {
            "valueId": "124",
            "eventId": "457",
            "timeRaw": int(datetime(2026, 11, 6, 15, 30, tzinfo=UTC).timestamp()),
        },
        7200,
    )
    assert current["scheduledAt"] == "2026-11-06T13:30:00+00:00"
    assert current["barProfileScheduledAt"] == current["scheduledAt"]
    windows = week_ranges(date(2026, 11, 4), 7200)
    assert windows[0]["toRaw"] - windows[0]["fromRaw"] == 7 * 86400
    for window in windows:
        for key, raw in (("from", "fromRaw"), ("to", "toRaw")):
            assert datetime.fromtimestamp(window[raw] - 7200, UTC).isoformat() == window[key]


def test_calendar_offset_must_match_whole_hour_vantage_session_clock() -> None:
    assert calendar_offset_seconds({"serverTime": 10000, "utcTime": 2800}) == 7200
    assert calendar_offset_seconds({"serverTime": 10001, "utcTime": 2800}) == 7200
    assert calendar_offset_seconds({"serverTime": 20000, "utcTime": 9200}) == 10800
    with pytest.raises(ValueError, match="offset"):
        calendar_offset_seconds({"serverTime": 10003, "utcTime": 2800})
    with pytest.raises(ValueError, match="offset"):
        calendar_offset_seconds({"serverTime": 10000, "utcTime": 10000})


async def test_shutdown_writes_evidence_while_authenticated_client_remains_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = asyncio.Event()
    actual_start = asyncio.start_server
    address: tuple[str, int] | None = None

    async def start_server(*args: Any, **kwargs: Any) -> asyncio.Server:
        nonlocal address
        server = await actual_start(*args, **kwargs)
        address = server.sockets[0].getsockname()[:2]
        started.set()
        return server

    async def stop_at_first_query(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise ValueError("Native query intentionally failed for shutdown regression")

    monkeypatch.setattr(poc.asyncio, "start_server", start_server)
    monkeypatch.setattr(poc.Collector, "query", stop_at_first_query)
    token_file = tmp_path / "test-token"
    token = "synthetic-test-token-" + "a" * 32
    token_file.write_text(token)
    output = tmp_path / "evidence.json"
    args = argparse.Namespace(
        token_file=token_file,
        output=output,
        anchor_date=date(2026, 11, 4),
        host="127.0.0.1",
        port=0,
        connect_timeout=2,
        baseline_seconds=0,
        recovery_seconds=0,
        query_timeout=1,
    )

    async def invoke() -> int | None:
        try:
            await poc.run(args)
        except SystemExit as exc:
            return exc.code
        return None

    task = asyncio.create_task(invoke())
    await asyncio.wait_for(started.wait(), 2)
    assert address is not None
    _, writer = await asyncio.open_connection(*address)
    try:
        now = datetime.now(UTC)
        hello = {
            "type": "hello",
            "version": 1,
            "server": "VantageMarkets-Demo",
            "service": True,
            "algoTrading": False,
            "symbols": ["XAUUSD", "EURUSD"],
            "serverTime": int(to_broker_wall(now).timestamp()),
            "utcTime": int(now.timestamp()),
        }
        writer.write(f"HELLO {token}\n{json.dumps(hello)}\n".encode())
        await writer.drain()
        assert await asyncio.wait_for(task, 2) == 1
        evidence = json.loads(output.read_text())
        assert "intentionally failed" in evidence["failure"]
        assert evidence["connectionErrors"] == []
    finally:
        writer.close()
        await writer.wait_closed()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
