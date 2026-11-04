import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.errors import ProviderUnavailableError
from app.providers.mt5_calendar import MT5CalendarProvider


async def connect(provider, *, role="calendar"):
    port = provider._server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    now = int(datetime.now(UTC).timestamp())
    writer.write(b"HELLO " + b"t" * 40 + b"\n")
    writer.write(
        json.dumps(
            {
                "type": "hello",
                "version": 1,
                "server": "VantageMarkets-Demo",
                "symbols": ["XAUUSD"],
                "role": role,
                "service": True,
                "algoTrading": False,
                "serverTime": now + 7200,
                "utcTime": now,
            }
        ).encode()
        + b"\n"
    )
    await writer.drain()
    return reader, writer


def provider_for(tmp_path, timeout=0.5):
    token = tmp_path / "token"
    token.write_text("t" * 40)
    return MT5CalendarProvider(token_file=token, host="127.0.0.1", port=0, timeout_seconds=timeout)


async def response(reader, writer, *, incomplete=False):
    command = (await reader.readline()).decode().strip().split("\t")
    assert command[0] == "CALENDAR" and command[4] == "ALL"
    _, identifier, start, end, _ = command
    now = int(datetime.now(UTC).timestamp())
    rows = [
        {
            "type": "calendar_begin",
            "id": identifier,
            "nativeCount": 2 if incomplete else 1,
            "fromRaw": int(start),
            "toRaw": int(end),
            "error": 0,
            "serverTimeBefore": now + 7200,
            "utcTimeBefore": now,
            "serverTimeAfter": now + 7200,
            "utcTimeAfter": now,
        },
        {"type": "calendar_event", "id": identifier, "valueId": start, "timeRaw": int(start)},
        {
            "type": "calendar_end",
            "id": identifier,
            "error": 0,
            "phase": "complete",
            "metadataFailures": 0,
            "count": 1,
            "outOfRangeCount": 0,
        },
    ]
    for row in rows:
        writer.write(json.dumps(row).encode() + b"\n")
    await writer.drain()
    return int(start), int(end)


@pytest.mark.asyncio
async def test_calendar_splits_range_and_uses_session_offset_across_dst(tmp_path):
    provider = provider_for(tmp_path)
    await provider.start()
    reader, writer = await connect(provider)
    start = datetime(2026, 10, 26, tzinfo=UTC)
    task = asyncio.create_task(provider.fetch_rows(start, start + timedelta(days=9)))
    first = await response(reader, writer)
    second = await response(reader, writer)
    rows = await task
    assert first == (int(start.timestamp()) + 7200, int(start.timestamp()) + 7200 + 7 * 86400)
    assert second[0] == first[1] and second[1] - second[0] == 2 * 86400
    assert rows[0]["scheduledAt"] == start
    assert rows[1]["scheduledAt"] == start + timedelta(days=7)
    await asyncio.wait_for(provider.close(), 1)
    assert await reader.read() == b""
    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_partial_calendar_response_is_failure_not_empty_success(tmp_path):
    provider = provider_for(tmp_path)
    await provider.start()
    reader, writer = await connect(provider)
    start = datetime.now(UTC)
    task = asyncio.create_task(provider.fetch_rows(start, start + timedelta(days=1)))
    await response(reader, writer, incomplete=True)
    with pytest.raises(ProviderUnavailableError):
        await task
    await provider.close()
    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_calendar_timeout_and_wrong_service_role_fail_closed(tmp_path):
    provider = provider_for(tmp_path, timeout=0.05)
    await provider.start()
    reader, writer = await connect(provider, role="quotes")
    assert await asyncio.wait_for(reader.read(), 1) == b""
    start = datetime.now(UTC)
    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_rows(start, start + timedelta(days=1))
    assert not provider._ready.is_set()
    writer.close()
    await writer.wait_closed()
    await provider.close()


def test_native_mapping_keeps_id_namespace_missing_fields_and_revised_previous():
    from app.providers.mt5_calendar import normalize_event

    now = datetime.now(UTC)
    row = {
        "valueId": "123",
        "name": "JOLTS",
        "currency": "USD",
        "importance": 3,
        "unit": 7,
        "multiplier": 2,
        "digits": 3,
        "scheduledAt": now,
        "actualRaw": "7523000",
        "forecastRaw": "6779000",
        "previousRaw": "7079000",
        "revisedPreviousRaw": "7190000",
    }
    event = normalize_event(row)
    assert event.external_event_id == "mt5:123" and event.calendar_type == "FOREX"
    assert (event.actual, event.forecast, event.previous, event.revision) == (
        "7.523M",
        "6.779M",
        "7.079M",
        "7.190M",
    )
    assert (
        event.description is None and event.news_url is None and event.actual_better_worse is None
    )
    row.update(unit=1, multiplier=0, digits=1, actualRaw="0", forecastRaw=None)
    assert normalize_event(row).actual == "0.0%"
    assert normalize_event(row).forecast is None
    row["actualRaw"] = "NaN"
    with pytest.raises(ValueError):
        normalize_event(row)


@pytest.mark.asyncio
async def test_quote_shutdown_closes_a_persistent_client_before_waiting_for_server(tmp_path):
    from app.providers.mt5 import MT5Provider
    from tests.unit.test_mt5_integration import symbol

    token = tmp_path / "token"
    token.write_text("t" * 40)
    provider = MT5Provider([symbol()], token_file=token, host="127.0.0.1", port=0)
    await provider.start()
    reader, writer = await connect(provider)
    async with asyncio.timeout(1):
        while provider._writer is None:
            await asyncio.sleep(0.01)
    await asyncio.wait_for(provider.close(), 1)
    assert await reader.read() == b""
    writer.close()
    await writer.wait_closed()
