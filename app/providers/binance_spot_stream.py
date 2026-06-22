import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast

from binance_common.configuration import ConfigurationWebSocketStreams
from binance_sdk_spot.spot import Spot
from binance_sdk_spot.websocket_streams.models import KlineIntervalEnum

from app.domain.candles import Candle
from app.domain.errors import ProviderUnavailableError
from app.domain.quotes import Quote
from app.domain.streams import (
    CandleInterest,
    ProviderSignal,
    ProviderStreamEvent,
    QuoteInterest,
    StreamCandle,
    StreamInterest,
    StreamQuote,
)
from app.domain.symbols import SupportedSymbol
from app.domain.timeframes import get_timeframe

logger = logging.getLogger(__name__)


class StreamHandle(Protocol):
    def on(self, event: str, callback: Callable[[object], None]) -> None: ...

    async def unsubscribe(self) -> None: ...


class BinanceWebSocketStreams(Protocol):
    connections: list[object]

    async def create_connection(self) -> object: ...

    async def ticker(self, symbol: str) -> StreamHandle: ...

    async def kline(self, symbol: str, interval: KlineIntervalEnum) -> StreamHandle: ...

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
        interest = QuoteInterest(symbol.symbol)
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
                raise ProviderUnavailableError from exc
            self._symbols[symbol.provider_symbol] = symbol
            self._handles[interest] = handle

    async def subscribe_candle(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
    ) -> None:
        interest = CandleInterest(symbol.symbol, timeframe)
        interval = _KLINE_INTERVALS.get(provider_interval)
        if interval is None:
            raise ProviderUnavailableError
        async with self._lock:
            if interest in self._handles:
                return
            await self._ensure_connected()
            try:
                handle = await self._streams.kline(
                    symbol.provider_symbol.lower(),
                    interval,
                )
                handle.on("message", self._candle_callback(symbol, timeframe))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                raise ProviderUnavailableError from exc
            self._symbols[symbol.provider_symbol] = symbol
            self._handles[interest] = handle

    async def unsubscribe(self, interest: StreamInterest) -> None:
        async with self._lock:
            handle = self._handles.pop(interest, None)
            if handle is None:
                return
            try:
                await handle.unsubscribe()
            except Exception:
                logger.warning("binance_stream_unsubscribe_failed", exc_info=True)
            if not self._handles:
                await self._close_connection()

    async def close(self) -> None:
        async with self._lock:
            handles = list(self._handles.values())
            self._handles.clear()
            for handle in handles:
                try:
                    await handle.unsubscribe()
                except Exception:
                    logger.warning("binance_stream_unsubscribe_failed", exc_info=True)
            await self._close_connection()

    async def _ensure_connected(self) -> None:
        if self._connected and self._streams.connections:
            return
        try:
            await self._streams.create_connection()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError from exc
        if not self._streams.connections:
            raise ProviderUnavailableError
        self._connected = True

    async def _close_connection(self) -> None:
        if not self._connected and not self._streams.connections:
            return
        try:
            await self._streams.close_connection()
        except Exception:
            logger.warning("binance_stream_close_failed", exc_info=True)
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
                logger.warning(
                    "binance_stream_ticker_rejected",
                    extra={"symbol": symbol.symbol},
                )

        return callback

    def _candle_callback(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
    ) -> Callable[[object], None]:
        def callback(payload: object) -> None:
            try:
                provider_symbol = _field(payload, "s")
                event_ms = _integer_field(payload, "E")
                kline = getattr(payload, "k", None)
                timeframe_model = get_timeframe(timeframe)
                if (
                    provider_symbol != symbol.provider_symbol
                    or event_ms is None
                    or kline is None
                    or timeframe_model is None
                    or _field(kline, "s") != symbol.provider_symbol
                    or _field(kline, "i") != timeframe_model.provider_interval
                ):
                    raise ValueError
                open_ms = _integer_field(kline, "t")
                close_ms = _integer_field(kline, "T")
                complete = getattr(kline, "x", None)
                values = (
                    _decimal_field(kline, "o", positive=True),
                    _decimal_field(kline, "h", positive=True),
                    _decimal_field(kline, "l", positive=True),
                    _decimal_field(kline, "c", positive=True),
                    _decimal_field(kline, "v", positive=False),
                )
                if (
                    open_ms is None
                    or close_ms is None
                    or not isinstance(complete, bool)
                    or any(value is None for value in values)
                ):
                    raise ValueError
                open_time = datetime.fromtimestamp(open_ms / 1000, tz=UTC)
                close_time = datetime.fromtimestamp(close_ms / 1000, tz=UTC)
                expected_close = open_time + timeframe_model.duration - timedelta(milliseconds=1)
                open_price, high, low, close, volume = cast(tuple[Decimal, ...], values)
                if (
                    close_time != expected_close
                    or high < max(open_price, close)
                    or low > min(open_price, close)
                    or high < low
                ):
                    raise ValueError
                received_at = datetime.now(UTC)
                self.events.put_nowait(
                    StreamCandle(
                        Candle(
                            symbol=symbol.symbol,
                            asset_class=symbol.asset_class,
                            provider=symbol.provider,
                            provider_symbol=symbol.provider_symbol,
                            timeframe=timeframe,
                            open_time=open_time,
                            close_time=close_time,
                            open=open_price,
                            high=high,
                            low=low,
                            close=close,
                            volume=volume,
                            complete=complete,
                        ),
                        received_at,
                    )
                )
            except ValueError, asyncio.QueueFull:
                logger.warning(
                    "binance_stream_kline_rejected",
                    extra={"symbol": symbol.symbol, "timeframe": timeframe},
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
            logger.warning("binance_stream_signal_dropped")


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


_KLINE_INTERVALS = {
    "1m": KlineIntervalEnum.INTERVAL_1m,
    "5m": KlineIntervalEnum.INTERVAL_5m,
    "15m": KlineIntervalEnum.INTERVAL_15m,
    "1h": KlineIntervalEnum.INTERVAL_1h,
    "1d": KlineIntervalEnum.INTERVAL_1d,
}
