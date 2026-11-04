"""Authenticated local TCP adapter for a chart-independent MQL5 Service."""

import asyncio
import hmac
import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import ceil
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.candles import Candle
from app.domain.errors import ProviderUnavailableError
from app.domain.mt5_time import from_broker_wall, to_broker_wall
from app.domain.quotes import ProviderQuoteBatch, Quote
from app.domain.streams import (
    ProviderSignal,
    ProviderStreamEvent,
    QuoteInterest,
    StreamInterest,
    StreamQuote,
)
from app.domain.symbols import SupportedSymbol
from app.domain.timeframes import candle_close_time, get_timeframe
from app.providers.normalization import parse_decimal

PROVIDER = "MT5_VANTAGE_DEMO"
FRAME_LIMIT = 65536
PAGE_SIZE = 128
logger = logging.getLogger(__name__)


def number(value: object, *, positive: bool = True) -> Decimal:
    parsed = parse_decimal(value, positive=positive)
    if parsed is None:
        raise ValueError("Invalid MT5 decimal")
    return parsed


def integer(value: object) -> int:
    if type(value) is not int:
        raise ValueError("Invalid MT5 integer")
    return value


class MT5Provider:
    def __init__(
        self,
        symbols: list[SupportedSymbol],
        *,
        token_file: Path,
        host: str,
        port: int,
        timeout_seconds: float = 15,
        queue_capacity: int = 1024,
    ) -> None:
        self.symbols = {s.provider_symbol: s for s in symbols}
        if any(any(c in name for c in "\t\r\n") for name in self.symbols):
            raise ValueError("Invalid MT5 registry symbol")
        self.events: asyncio.Queue[ProviderStreamEvent] = asyncio.Queue(queue_capacity)
        self._token = token_file.read_text().strip()
        if len(self._token) < 32 or not self.symbols:
            raise ValueError("MT5 requires a private token and registry mappings")
        self._host, self._port = host, port
        self._timeout = timeout_seconds
        self._server: asyncio.Server | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._clients: set[asyncio.Task[Any]] = set()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._rpc_lock = asyncio.Lock()
        self._latest: dict[str, Quote] = {}
        self._connected = False
        self._last_sequence = 0
        self.rpc_count = 0
        self.tick_count = 0
        self.connection_count = 0

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._accept, self._host, self._port, limit=FRAME_LIMIT
        )

    async def _line(self, reader: asyncio.StreamReader) -> bytes:
        line = await asyncio.wait_for(reader.readline(), 30)
        if not line or len(line) > FRAME_LIMIT or not line.endswith(b"\n"):
            raise ValueError("Invalid MT5 frame")
        return line.rstrip(b"\r\n")

    async def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._clients.add(task)
        owned = False
        try:
            first = await asyncio.wait_for(self._line(reader), 5)
            if not hmac.compare_digest(first, f"HELLO {self._token}".encode()) or self._writer:
                return
            hello = json.loads(await asyncio.wait_for(self._line(reader), 5))
            now = datetime.now(UTC)
            if (
                hello.get("type") != "hello"
                or hello.get("version") != 1
                or hello.get("server") != "VantageMarkets-Demo"
                or hello.get("service") is not True
                or hello.get("algoTrading") is not False
            ):
                raise ValueError("MT5 handshake mismatch")
            server_utc = from_broker_wall(datetime.fromtimestamp(integer(hello["serverTime"]), UTC))
            terminal_utc = datetime.fromtimestamp(integer(hello["utcTime"]), UTC)
            if (
                abs((server_utc - now).total_seconds()) > 15
                or abs((terminal_utc - now).total_seconds()) > 15
            ):
                raise ValueError("MT5 clock mismatch")
            if set(hello["symbols"]) != set(self.symbols) or self._writer is not None:
                raise ValueError("MT5 symbol allowlist mismatch")
            self._writer = writer
            self._connected = True
            self._last_sequence = 0
            self.connection_count += 1
            owned = True
            while True:
                message = json.loads(await self._line(reader))
                kind = message.get("type")
                if kind == "tick":
                    await self._tick(message)
                elif kind == "rates":
                    future = self._pending.get(message.get("id", ""))
                    if future is not None and not future.done():
                        future.set_result(message)
                elif kind == "status" and type(message.get("connected")) is bool:
                    was_connected = self._connected
                    self._connected = message["connected"]
                    if was_connected and not self._connected:
                        await self._signal()
                else:
                    raise ValueError("Unknown MT5 message")
        except (
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            TimeoutError,
            OSError,
            OverflowError,
        ):
            logger.warning("MT5 connection closed: invalid frame, clock, timeout or disconnect")
        finally:
            if owned:
                self._writer = None
                self._connected = False
                for future in self._pending.values():
                    if not future.done():
                        future.set_exception(
                            ProviderUnavailableError(failure_reason="REQUEST_FAILED")
                        )
                await self._signal()
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
            if task is not None:
                self._clients.discard(task)

    async def _signal(self) -> None:
        signal = ProviderSignal(
            "RECONNECTING",
            tuple(
                QuoteInterest(s.symbol, s.provider, s.provider_symbol)
                for s in self.symbols.values()
            ),
            datetime.now(UTC),
        )
        try:
            self.events.put_nowait(signal)
        except asyncio.QueueFull:
            logger.warning("MT5 status queue full")

    async def _tick(self, message: dict[str, Any]) -> None:
        symbol = self.symbols[message["symbol"]]
        sequence = integer(message["seq"])
        if sequence <= self._last_sequence:
            raise ValueError("MT5 sequence went backwards")
        self._last_sequence = sequence
        if message.get("connected") is not True:
            return
        timestamp = from_broker_wall(
            datetime.fromtimestamp(integer(message["timeMscRaw"]) / 1000, UTC)
        )
        received = datetime.now(UTC)
        if timestamp > received + timedelta(seconds=5):
            raise ValueError("MT5 quote is in the future")
        bid = number(message["bid"])
        number(message["ask"])
        previous = self._latest.get(symbol.provider_symbol)
        if previous is not None and previous.provider_time is not None:
            if timestamp < previous.provider_time or (
                timestamp == previous.provider_time and bid == previous.price
            ):
                return
        quote = Quote(
            symbol.symbol,
            symbol.asset_class,
            PROVIDER,
            symbol.provider_symbol,
            bid,
            None,
            timestamp,
            received,
            freshness_at=timestamp,
        )
        self._latest[symbol.provider_symbol] = quote
        self.tick_count += 1
        try:
            await asyncio.wait_for(self.events.put(StreamQuote(quote)), 1)
        except TimeoutError as exc:
            raise ValueError("MT5 ingestion backpressure") from exc

    async def fetch_latest_prices(self, provider_symbols: list[str]) -> ProviderQuoteBatch:
        quotes = {
            s: self._latest[s] for s in provider_symbols if self._connected and s in self._latest
        }
        return ProviderQuoteBatch(
            {s: q.price for s, q in quotes.items()},
            frozenset(set(provider_symbols) - quotes.keys()),
            {(PROVIDER, s): q for s, q in quotes.items()},
        )

    async def subscribe_quote(self, symbol: SupportedSymbol) -> None:
        if symbol.provider_symbol not in self.symbols:
            raise ProviderUnavailableError(failure_reason="PROVIDER_NOT_CONFIGURED")
        quote = self._latest.get(symbol.provider_symbol)
        if quote is not None and self._connected:
            await self.events.put(StreamQuote(quote))

    async def unsubscribe(self, interest: StreamInterest) -> None:
        pass  # Capture remains active without subscribers.

    async def fetch_candles(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[Candle]:
        frame = get_timeframe(timeframe)
        if frame is None or symbol.provider_symbol not in self.symbols:
            raise ProviderUnavailableError(failure_reason="INVALID_RESPONSE")
        rows: list[Candle] = []
        cursor = start
        try:
            async with asyncio.timeout(self._timeout):
                async with self._rpc_lock:
                    while cursor < end:
                        writer = self._writer
                        if writer is None or not self._connected:
                            raise ValueError("MT5 is disconnected")
                        request_id = uuid4().hex
                        future: asyncio.Future[dict[str, Any]] = (
                            asyncio.get_running_loop().create_future()
                        )
                        self._pending[request_id] = future
                        native_start = ceil(to_broker_wall(cursor).timestamp())
                        native_end = ceil(to_broker_wall(end).timestamp())
                        command = (
                            f"RATES\t{request_id}\t{symbol.provider_symbol}\t{timeframe}\t"
                            f"{native_start}\t{native_end}\t{PAGE_SIZE}\n"
                        )
                        writer.write(command.encode())
                        self.rpc_count += 1
                        try:
                            await writer.drain()
                            result = await future
                        finally:
                            self._pending.pop(request_id, None)
                        if result.get("status") == "LOADING":
                            await asyncio.sleep(0.2)
                            continue
                        if result.get("status") != "OK" or result.get("error") != 0:
                            raise ValueError("MT5 history loading or failed")
                        bars = result["bars"]
                        if not isinstance(bars, list) or len(bars) > PAGE_SIZE:
                            raise ValueError("MT5 history page too large")
                        logger.debug(
                            "MT5 page %s %s rows=%s first=%s last=%s",
                            symbol.symbol,
                            timeframe,
                            len(bars),
                            bars[0].get("timeRaw") if bars else None,
                            bars[-1].get("timeRaw") if bars else None,
                        )
                        previous_time = cursor - timedelta(microseconds=1)
                        for bar in bars:
                            raw_open = datetime.fromtimestamp(integer(bar["timeRaw"]), UTC)
                            opened = from_broker_wall(raw_open)
                            close_raw = candle_close_time(raw_open, frame)
                            closed = from_broker_wall(close_raw)
                            if opened <= previous_time or not cursor <= opened < end:
                                raise ValueError("MT5 returned unordered or out-of-range candles")
                            o, h, low, c = (number(bar[k]) for k in ("o", "h", "l", "c"))
                            if not low <= min(o, c) <= max(o, c) <= h:
                                raise ValueError("MT5 returned invalid OHLC")
                            rows.append(
                                Candle(
                                    symbol.symbol,
                                    symbol.asset_class,
                                    PROVIDER,
                                    symbol.provider_symbol,
                                    timeframe,
                                    opened,
                                    closed,
                                    o,
                                    h,
                                    low,
                                    c,
                                    number(bar["volume"], positive=False),
                                    closed <= datetime.now(UTC),
                                )
                            )
                            previous_time = opened
                        if len(bars) < PAGE_SIZE:
                            break
                        cursor = rows[-1].open_time + timedelta(seconds=1)
        except (
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            TimeoutError,
            OSError,
            OverflowError,
        ) as exc:
            logger.warning(
                "MT5 candle request failed: %s %s %s", symbol.symbol, timeframe, str(exc)
            )
            raise ProviderUnavailableError(
                failure_reason="INVALID_RESPONSE", retryable=True
            ) from exc
        return rows

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
        if self._writer is not None:
            self._writer.close()
        tasks = list(self._clients)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self._server is not None:
            await self._server.wait_closed()
