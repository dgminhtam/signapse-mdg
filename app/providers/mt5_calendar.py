"""Economic-calendar RPC on a dedicated authenticated MQL5 Service connection."""

import asyncio
import hmac
import json
import logging
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.economic_calendar import EconomicCalendarFetchedEvent
from app.domain.errors import ProviderUnavailableError
from app.providers.mt5 import FRAME_LIMIT, integer

logger = logging.getLogger(__name__)


def session_offset(
    message: dict[str, Any], server_key: str, utc_key: str, *, fresh: bool = True
) -> int:
    server, utc = integer(message[server_key]), integer(message[utc_key])
    offset = round((server - utc) / 3600) * 3600
    if offset not in (7200, 10800) or abs(server - utc - offset) > 2:
        raise ValueError("Unexpected calendar broker clock")
    if fresh and abs(datetime.now(UTC).timestamp() - utc) > 15:
        raise ValueError("Stale calendar clock")
    return offset


def normalize_event(row: dict[str, Any]) -> EconomicCalendarFetchedEvent:
    identifier = row["valueId"]
    if not isinstance(identifier, str) or not re.fullmatch(r"[0-9]{1,20}", identifier):
        raise ValueError("Invalid MT5 calendar identity")
    name, currency = row["name"], row["currency"]
    if not isinstance(name, str) or not name.strip() or len(name) > 1000:
        raise ValueError("Invalid calendar name")
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("Invalid calendar currency")
    importance, unit, multiplier, digits = (
        integer(row[k]) for k in ("importance", "unit", "multiplier", "digits")
    )
    if (
        not 0 <= importance <= 3
        or not 0 <= unit <= 13
        or not 0 <= multiplier <= 4
        or not 0 <= digits <= 6
    ):
        raise ValueError("Invalid calendar numeric metadata")

    def value(field: str) -> str | None:
        raw = row[field]
        if raw is None or raw == "-9223372036854775808":
            return None
        if not isinstance(raw, str) or not re.fullmatch(r"-?[0-9]{1,20}", raw):
            raise ValueError("Invalid calendar fixed-point value")
        number = int(raw)
        if not -(2**63) < number < 2**63:
            raise ValueError("Calendar value overflow")
        text = format(Decimal(number) / Decimal(1_000_000), f".{digits}f")
        return text + ("", "K", "M", "B", "T")[multiplier] + ("%" if unit == 1 else "")

    scheduled = row["scheduledAt"]
    if not isinstance(scheduled, datetime) or scheduled.tzinfo is None:
        raise ValueError("Invalid calendar UTC timestamp")
    return EconomicCalendarFetchedEvent(
        calendar_type="FOREX",
        external_event_id=f"mt5:{identifier}",
        name=name.strip(),
        currency=currency,
        impact=(None, "LOW", "MEDIUM", "HIGH")[importance],
        scheduled_at=scheduled,
        actual=value("actualRaw"),
        forecast=value("forecastRaw"),
        previous=value("previousRaw"),
        revision=value("revisedPreviousRaw"),
        actual_better_worse=None,
        revision_better_worse=None,
    )


class MT5CalendarProvider:
    def __init__(
        self, *, token_file: Path, host: str, port: int, timeout_seconds: float = 60
    ) -> None:
        self._token = token_file.read_text().strip()
        if len(self._token) < 32:
            raise ValueError("MT5 calendar requires a private token")
        self._host, self._port, self._timeout = host, port, timeout_seconds
        self._server: asyncio.Server | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._clients: set[asyncio.Task[Any]] = set()
        self._ready = asyncio.Event()
        self._lock = asyncio.Lock()
        self._offset = 0
        self._request_id: str | None = None
        self._bounds = (0, 0)
        self._future: asyncio.Future[list[dict[str, Any]]] | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._accept, self._host, self._port, limit=FRAME_LIMIT
        )

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
        clients = list(self._clients)
        for task in clients:
            task.cancel()
        await asyncio.gather(*clients, return_exceptions=True)
        if self._server is not None:
            await self._server.wait_closed()

    async def _line(self, reader: asyncio.StreamReader) -> bytes:
        line = await asyncio.wait_for(reader.readline(), self._timeout + 5)
        if not line or len(line) > FRAME_LIMIT or not line.endswith(b"\n"):
            raise ValueError("Invalid calendar frame")
        return line.rstrip(b"\r\n")

    async def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._clients.add(task)
        owned = False
        try:
            auth = await asyncio.wait_for(self._line(reader), 5)
            if not hmac.compare_digest(auth, f"HELLO {self._token}".encode()) or self._writer:
                return
            hello = json.loads(await asyncio.wait_for(self._line(reader), 5))
            if not isinstance(hello, dict):
                raise ValueError("Invalid calendar handshake")
            if (
                hello.get("type") != "hello"
                or hello.get("version") != 1
                or hello.get("server") != "VantageMarkets-Demo"
                or hello.get("role") != "calendar"
                or hello.get("service") is not True
                or hello.get("algoTrading") is not False
            ):
                raise ValueError("Calendar handshake mismatch")
            self._offset = session_offset(hello, "serverTime", "utcTime")
            self._writer, owned = writer, True
            self._ready.set()
            header: dict[str, Any] | None = None
            rows: list[dict[str, Any]] = []
            ids: set[str] = set()
            while True:
                message = json.loads(await self._line(reader))
                if not isinstance(message, dict):
                    raise ValueError("Invalid calendar object")
                kind = message.get("type")
                if kind == "status" and type(message.get("connected")) is bool:
                    if message["connected"]:
                        self._ready.set()
                    else:
                        self._ready.clear()
                        if self._future is not None and not self._future.done():
                            raise ValueError("Calendar broker disconnected")
                    continue
                if message.get("id") != self._request_id or self._future is None:
                    raise ValueError("Unexpected calendar request ID")
                if kind == "calendar_begin":
                    if header is not None or message.get("error") != 0:
                        raise ValueError("Calendar fetch failed")
                    for server_key, utc_key, fresh in (
                        ("serverTimeBefore", "utcTimeBefore", False),
                        ("serverTimeAfter", "utcTimeAfter", True),
                    ):
                        if (
                            session_offset(message, server_key, utc_key, fresh=fresh)
                            != self._offset
                        ):
                            raise ValueError("Calendar offset changed during request")
                    if (message.get("fromRaw"), message.get("toRaw")) != self._bounds:
                        raise ValueError("Calendar response range mismatch")
                    if not 0 <= integer(message["nativeCount"]) <= 10000:
                        raise ValueError("Calendar row limit exceeded")
                    header = message
                elif kind == "calendar_event" and header is not None:
                    identifier = message.get("valueId")
                    if (
                        not isinstance(identifier, str)
                        or not identifier.isdigit()
                        or len(identifier) > 20
                        or identifier in ids
                        or len(rows) >= 10000
                    ):
                        raise ValueError("Invalid or duplicate calendar occurrence")
                    ids.add(identifier)
                    rows.append(message)
                elif kind == "calendar_end" and header is not None:
                    if (
                        message.get("error") != 0
                        or message.get("phase") != "complete"
                        or message.get("metadataFailures") != 0
                        or integer(message["count"]) != len(rows)
                        or integer(header["nativeCount"]) - integer(message["outOfRangeCount"])
                        != len(rows)
                    ):
                        raise ValueError("Incomplete calendar response")
                    if not self._future.done():
                        self._future.set_result(rows)
                    header, rows, ids = None, [], set()
                else:
                    raise ValueError("Invalid calendar response")
        except OSError, ValueError, KeyError, TypeError, OverflowError, TimeoutError:
            logger.warning("MT5 calendar connection closed: frame, clock, timeout or disconnect")
        finally:
            if owned:
                self._writer = None
                self._ready.clear()
                if self._future is not None and not self._future.done():
                    self._future.set_exception(
                        ProviderUnavailableError(provider="MT5_CALENDAR", retryable=True)
                    )
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
            if task is not None:
                self._clients.discard(task)

    async def fetch_rows(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ValueError("Calendar requires an aware increasing time range")
        result: list[dict[str, Any]] = []
        async with self._lock:
            while start < end:
                stop = min(end, start + timedelta(days=7))
                try:
                    async with asyncio.timeout(self._timeout):
                        await self._ready.wait()
                        writer = self._writer
                        if writer is None:
                            raise ProviderUnavailableError(provider="MT5_CALENDAR", retryable=True)
                        self._request_id = uuid4().hex
                        self._future = asyncio.get_running_loop().create_future()
                        native_from = int(start.timestamp()) + self._offset
                        native_to = int(stop.timestamp()) + self._offset
                        self._bounds = (native_from, native_to)
                        writer.write(
                            f"CALENDAR\t{self._request_id}\t{native_from}\t{native_to}\tALL\n".encode()
                        )
                        await writer.drain()
                        rows = await self._future
                        for row in rows:
                            native = integer(row["timeRaw"])
                            if not native_from <= native < native_to:
                                raise ValueError("Calendar event outside requested window")
                            row["scheduledAt"] = datetime.fromtimestamp(native - self._offset, UTC)
                        result.extend(rows)
                except (
                    TimeoutError,
                    ValueError,
                    OSError,
                    KeyError,
                    TypeError,
                    OverflowError,
                ) as exc:
                    if self._writer is not None:
                        self._writer.close()
                    raise ProviderUnavailableError(
                        "MT5 calendar is unavailable.",
                        provider="MT5_CALENDAR",
                        failure_reason="REQUEST_FAILED",
                        retryable=True,
                    ) from exc
                finally:
                    self._request_id, self._future = None, None
                start = stop
        if len({r["valueId"] for r in result}) != len(result):
            raise ProviderUnavailableError(
                "Duplicate calendar occurrences.", provider="MT5_CALENDAR"
            )
        return result

    async def fetch_events(
        self, calendar_type: str, start: datetime, end: datetime
    ) -> list[EconomicCalendarFetchedEvent]:
        if calendar_type != "FOREX":
            raise ValueError("MT5 macro calendar is mapped to FOREX only")
        try:
            return [normalize_event(row) for row in await self.fetch_rows(start, end)]
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            raise ProviderUnavailableError(
                "Invalid MT5 calendar data.",
                provider="MT5_CALENDAR",
                failure_reason="INVALID_PROVIDER_DATA",
                retryable=False,
            ) from exc
