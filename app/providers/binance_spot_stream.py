import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast

from binance_common.configuration import ConfigurationWebSocketStreams
from binance_sdk_spot.spot import Spot

from app.core.observability import failure_metadata, log_failure, log_rate_limited_warning
from app.domain.errors import ProviderUnavailableError
from app.domain.quotes import Quote
from app.domain.streams import (
    ProviderSignal,
    ProviderStreamEvent,
    QuoteInterest,
    StreamInterest,
    StreamQuote,
)
from app.domain.symbols import SupportedSymbol

logger = logging.getLogger(__name__)


class StreamHandle(Protocol):
    def on(self, event: str, callback: Callable[[object], None]) -> None: ...

    async def unsubscribe(self) -> None: ...


class BinanceWebSocketStreams(Protocol):
    connections: list[object]

    async def create_connection(self) -> object: ...

    async def ticker(self, symbol: str) -> StreamHandle: ...

    async def close_connection(self) -> None: ...


class BinanceSpotStreamProvider:
    def __init__(
        self,
        streams: BinanceWebSocketStreams,
        *,
        queue_capacity: int,
    ) -> None:
        self._streams = streams
        self.events: asyncio.Queue[ProviderStreamEvent] = asyncio.Queue(queue_capacity)
        self._handles: dict[StreamInterest, StreamHandle] = {}
        self._symbols: dict[str, SupportedSymbol] = {}
        self._lock = asyncio.Lock()
        self._connected = False

    async def subscribe_quote(self, symbol: SupportedSymbol) -> None:
        interest = QuoteInterest(symbol.symbol, symbol.provider, symbol.provider_symbol)
        async with self._lock:
            if interest in self._handles:
                return
            await self._ensure_connected()
            try:
                handle = await self._streams.ticker(symbol.provider_symbol.lower())
                handle.on("message", self._quote_callback(symbol))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                metadata = failure_metadata(exc)
                log_failure(
                    logger,
                    "binance_stream_quote_subscribe_failed",
                    exc,
                    operation="stream.subscribe_quote",
                    provider="BINANCE_SPOT",
                    provider_symbol=symbol.provider_symbol,
                    symbol=symbol.symbol,
                )
                raise ProviderUnavailableError(
                    operation="stream.subscribe_quote",
                    provider="BINANCE_SPOT",
                    provider_symbol=symbol.provider_symbol,
                    symbol=symbol.symbol,
                    failure_reason=str(metadata["failure_reason"]),
                    retryable=bool(metadata["retryable"]),
                ) from exc
            self._symbols[symbol.provider_symbol] = symbol
            self._handles[interest] = handle

    async def unsubscribe(self, interest: StreamInterest) -> None:
        async with self._lock:
            handle = self._handles.pop(interest, None)
            if handle is None:
                return
            try:
                await handle.unsubscribe()
            except Exception as exc:
                log_failure(
                    logger,
                    "binance_stream_unsubscribe_failed",
                    exc,
                    operation="stream.unsubscribe",
                    provider="BINANCE_SPOT",
                )
            if not self._handles:
                await self._close_connection()

    async def close(self) -> None:
        async with self._lock:
            handles = list(self._handles.values())
            self._handles.clear()
            for handle in handles:
                try:
                    await handle.unsubscribe()
                except Exception as exc:
                    log_failure(
                        logger,
                        "binance_stream_unsubscribe_failed",
                        exc,
                        operation="stream.unsubscribe",
                        provider="BINANCE_SPOT",
                    )
            await self._close_connection()

    async def _ensure_connected(self) -> None:
        if self._connected and self._streams.connections:
            return
        try:
            await self._streams.create_connection()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            metadata = failure_metadata(exc)
            log_failure(
                logger,
                "binance_stream_connect_failed",
                exc,
                operation="stream.connect",
                provider="BINANCE_SPOT",
            )
            raise ProviderUnavailableError(
                operation="stream.connect",
                provider="BINANCE_SPOT",
                failure_reason=str(metadata["failure_reason"]),
                retryable=bool(metadata["retryable"]),
            ) from exc
        if not self._streams.connections:
            error = ProviderUnavailableError(
                failure_reason="EMPTY_RESPONSE",
                operation="stream.connect",
                provider="BINANCE_SPOT",
            )
            log_failure(logger, "binance_stream_no_connection", error)
            raise error
        self._connected = True

    async def _close_connection(self) -> None:
        if not self._connected and not self._streams.connections:
            return
        try:
            await self._streams.close_connection()
        except Exception as exc:
            log_failure(
                logger,
                "binance_stream_close_failed",
                exc,
                operation="stream.close",
                provider="BINANCE_SPOT",
            )
        finally:
            self._connected = False

    def _quote_callback(self, symbol: SupportedSymbol) -> Callable[[object], None]:
        def callback(payload: object) -> None:
            try:
                provider_symbol = _field(payload, "s")
                event_ms = _integer_field(payload, "E")
                price = _decimal_field(payload, "c", positive=True)
                if provider_symbol != symbol.provider_symbol or event_ms is None or price is None:
                    raise ValueError
                received_at = datetime.now(UTC)
                event = StreamQuote(
                    Quote(
                        symbol=symbol.symbol,
                        asset_class=symbol.asset_class,
                        provider=symbol.provider,
                        provider_symbol=symbol.provider_symbol,
                        price=price,
                        volume=None,
                        provider_time=datetime.fromtimestamp(event_ms / 1000, tz=UTC),
                        received_at=received_at,
                    )
                )
                self.events.put_nowait(event)
            except ValueError, asyncio.QueueFull:
                log_rate_limited_warning(
                    logger,
                    "binance_stream_ticker_rejected",
                    key=f"BINANCE_SPOT:ticker_rejected:{symbol.symbol}",
                    provider="BINANCE_SPOT",
                    symbol=symbol.symbol,
                )

        return callback

    def emit_reconnecting(self) -> None:
        interests = tuple(self._handles)
        if interests:
            self._put_signal(ProviderSignal("RECONNECTING", interests, datetime.now(UTC)))

    def emit_error(self) -> None:
        interests = tuple(self._handles)
        if interests:
            self._put_signal(ProviderSignal("ERROR", interests, datetime.now(UTC)))

    def _put_signal(self, signal: ProviderSignal) -> None:
        try:
            self.events.put_nowait(signal)
        except asyncio.QueueFull:
            log_rate_limited_warning(
                logger,
                "binance_stream_signal_dropped",
                key="BINANCE_SPOT:signal_dropped",
                provider="BINANCE_SPOT",
            )


def build_binance_spot_stream_provider(
    base_url: str,
    reconnect_delay_seconds: float,
    queue_capacity: int,
) -> BinanceSpotStreamProvider:
    configuration = ConfigurationWebSocketStreams(
        stream_url=base_url.rstrip("/"),
        reconnect_delay=round(reconnect_delay_seconds * 1000),
    )
    sdk = Spot(config_ws_streams=configuration)
    return BinanceSpotStreamProvider(
        cast(BinanceWebSocketStreams, sdk.websocket_streams),
        queue_capacity=queue_capacity,
    )


def _field(payload: object, name: str) -> str | None:
    value = getattr(payload, name, None)
    return value if isinstance(value, str) else None


def _integer_field(payload: object, name: str) -> int | None:
    value = getattr(payload, name, None)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _decimal_field(payload: object, name: str, *, positive: bool) -> Decimal | None:
    value = _field(payload, name)
    if value is None:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    if not parsed.is_finite() or parsed < 0 or (positive and parsed <= 0):
        return None
    return parsed
