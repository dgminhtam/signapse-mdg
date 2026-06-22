import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast

from twelvedata import TDClient  # type: ignore[import-untyped]

from app.domain.candles import Candle
from app.domain.errors import ProviderUnavailableError
from app.domain.market_sessions import get_market_session_policy
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
from app.domain.timeframes import EPOCH, get_timeframe
from app.providers.twelvedata_market_data import SUPPORTED_TWELVEDATA_PROVIDER_SYMBOLS

logger = logging.getLogger(__name__)


class TwelveDataWebSocket(Protocol):
    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def subscribe(self, symbols: str | list[str]) -> None: ...

    def unsubscribe(self, symbols: str | list[str]) -> None: ...

    def heartbeat(self) -> None: ...


class TwelveDataStreamClient(Protocol):
    def websocket(self, **defaults: object) -> TwelveDataWebSocket: ...


@dataclass(frozen=True, slots=True)
class PriceTick:
    symbol: SupportedSymbol
    price: Decimal
    provider_time: datetime | None
    received_at: datetime


class TwelveDataCandleBuilder:
    def __init__(self) -> None:
        self._current: dict[tuple[str, str], Candle] = {}

    def apply_tick(
        self,
        tick: PriceTick,
        timeframe: str,
    ) -> list[StreamCandle]:
        model = get_timeframe(timeframe)
        if model is None:
            return []
        source_time = (tick.provider_time or tick.received_at).astimezone(UTC)
        bucket_open = _bucket_open(source_time, model.duration)
        policy = get_market_session_policy(tick.symbol)
        if not policy.is_eligible(bucket_open, timeframe):
            self._current.pop((tick.symbol.symbol, timeframe), None)
            return []

        close_time = bucket_open + model.duration - timedelta(milliseconds=1)
        key = (tick.symbol.symbol, timeframe)
        current = self._current.get(key)
        emitted: list[StreamCandle] = []
        if current is not None and bucket_open > current.open_time:
            completed = Candle(
                current.symbol,
                current.asset_class,
                current.provider,
                current.provider_symbol,
                current.timeframe,
                current.open_time,
                current.close_time,
                current.open,
                current.high,
                current.low,
                current.close,
                current.volume,
                True,
            )
            emitted.append(StreamCandle(completed, tick.received_at))
            current = None

        if current is None:
            current = Candle(
                tick.symbol.symbol,
                tick.symbol.asset_class,
                tick.symbol.provider,
                tick.symbol.provider_symbol,
                timeframe,
                bucket_open,
                close_time,
                tick.price,
                tick.price,
                tick.price,
                tick.price,
                Decimal("0"),
                False,
            )
        elif bucket_open == current.open_time:
            current = Candle(
                current.symbol,
                current.asset_class,
                current.provider,
                current.provider_symbol,
                current.timeframe,
                current.open_time,
                current.close_time,
                current.open,
                max(current.high, tick.price),
                min(current.low, tick.price),
                tick.price,
                current.volume,
                False,
            )
        else:
            return emitted

        self._current[key] = current
        emitted.append(StreamCandle(current, tick.received_at))
        return emitted


class TwelveDataMarketDataStreamProvider:
    def __init__(
        self,
        client_factory: Callable[[Callable[[object], None]], TwelveDataStreamClient],
        *,
        queue_capacity: int,
        heartbeat_seconds: float,
    ) -> None:
        self.events: asyncio.Queue[ProviderStreamEvent] = asyncio.Queue(queue_capacity)
        self._client_factory = client_factory
        self._heartbeat_seconds = heartbeat_seconds
        self._client: TwelveDataStreamClient | None = None
        self._websocket: TwelveDataWebSocket | None = None
        self._connected = False
        self._symbols_by_provider_symbol: dict[str, SupportedSymbol] = {}
        self._provider_symbol_refs: dict[str, int] = {}
        self._quote_interests: set[QuoteInterest] = set()
        self._candle_interests: dict[str, set[str]] = {}
        self._builder = TwelveDataCandleBuilder()
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None

    async def subscribe_quote(self, symbol: SupportedSymbol) -> None:
        if symbol.provider_symbol not in SUPPORTED_TWELVEDATA_PROVIDER_SYMBOLS:
            raise ProviderUnavailableError
        async with self._lock:
            await self._ensure_connected()
            interest = QuoteInterest(symbol.symbol)
            if interest in self._quote_interests:
                return
            await self._subscribe_provider_symbol(symbol)
            self._quote_interests.add(interest)

    async def subscribe_candle(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
    ) -> None:
        del provider_interval
        if symbol.provider_symbol not in SUPPORTED_TWELVEDATA_PROVIDER_SYMBOLS:
            raise ProviderUnavailableError
        if get_timeframe(timeframe) is None:
            raise ProviderUnavailableError
        async with self._lock:
            await self._ensure_connected()
            timeframes = self._candle_interests.setdefault(symbol.symbol, set())
            if timeframe in timeframes:
                return
            await self._subscribe_provider_symbol(symbol)
            timeframes.add(timeframe)
            if not get_market_session_policy(symbol).is_eligible(
                _bucket_open(datetime.now(UTC), get_timeframe(timeframe).duration),  # type: ignore[union-attr]
                timeframe,
            ):
                self._put_signal(
                    ProviderSignal(
                        "MARKET_CLOSED",
                        (CandleInterest(symbol.symbol, timeframe),),
                        datetime.now(UTC),
                    )
                )

    async def unsubscribe(self, interest: StreamInterest) -> None:
        async with self._lock:
            symbol = self._symbol_for_interest(interest)
            if symbol is None:
                return
            if isinstance(interest, QuoteInterest):
                self._quote_interests.discard(interest)
            else:
                timeframes = self._candle_interests.get(interest.symbol)
                if timeframes is not None:
                    timeframes.discard(interest.timeframe)
                    if not timeframes:
                        self._candle_interests.pop(interest.symbol, None)
            await self._unsubscribe_provider_symbol(symbol)
            if not self._quote_interests and not self._candle_interests:
                await self._disconnect()

    async def close(self) -> None:
        async with self._lock:
            self._quote_interests.clear()
            self._candle_interests.clear()
            self._provider_symbol_refs.clear()
            self._symbols_by_provider_symbol.clear()
            await self._disconnect()

    async def _ensure_connected(self) -> None:
        if self._connected and self._websocket is not None:
            return
        self._loop = asyncio.get_running_loop()
        try:
            self._client = self._client_factory(self._on_event)
            self._websocket = self._client.websocket(on_event=self._on_event)
            await asyncio.to_thread(self._websocket.connect)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError from exc
        self._connected = True
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(),
            name="twelvedata-market-data-stream-heartbeat",
        )

    async def _subscribe_provider_symbol(self, symbol: SupportedSymbol) -> None:
        refs = self._provider_symbol_refs.get(symbol.provider_symbol, 0)
        self._provider_symbol_refs[symbol.provider_symbol] = refs + 1
        self._symbols_by_provider_symbol[symbol.provider_symbol] = symbol
        if refs > 0:
            return
        websocket = self._require_websocket()
        try:
            await asyncio.to_thread(websocket.subscribe, symbol.provider_symbol)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._provider_symbol_refs.pop(symbol.provider_symbol, None)
            raise ProviderUnavailableError from exc

    async def _unsubscribe_provider_symbol(self, symbol: SupportedSymbol) -> None:
        refs = self._provider_symbol_refs.get(symbol.provider_symbol, 0)
        if refs <= 1:
            self._provider_symbol_refs.pop(symbol.provider_symbol, None)
            self._symbols_by_provider_symbol.pop(symbol.provider_symbol, None)
            websocket = self._websocket
            if websocket is not None:
                try:
                    await asyncio.to_thread(websocket.unsubscribe, symbol.provider_symbol)
                except Exception:
                    logger.warning("twelvedata_stream_unsubscribe_failed", exc_info=True)
        else:
            self._provider_symbol_refs[symbol.provider_symbol] = refs - 1

    async def _disconnect(self) -> None:
        task = self._heartbeat_task
        self._heartbeat_task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        websocket = self._websocket
        self._websocket = None
        self._client = None
        self._connected = False
        if websocket is not None:
            try:
                await asyncio.to_thread(websocket.disconnect)
            except Exception:
                logger.warning("twelvedata_stream_disconnect_failed", exc_info=True)

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_seconds)
            websocket = self._websocket
            if websocket is None:
                return
            try:
                await asyncio.to_thread(websocket.heartbeat)
            except Exception:
                self._put_signal(
                    ProviderSignal(
                        "RECONNECTING",
                        self._active_interests(),
                        datetime.now(UTC),
                    )
                )

    def _on_event(self, payload: object) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._handle_payload_on_loop, payload)

    def _handle_payload_on_loop(self, payload: object) -> None:
        tick = self._normalize_tick(payload)
        if tick is None:
            return
        quote_interest = QuoteInterest(tick.symbol.symbol)
        if quote_interest in self._quote_interests:
            self._put_event(
                StreamQuote(
                    Quote(
                        tick.symbol.symbol,
                        tick.symbol.asset_class,
                        tick.symbol.provider,
                        tick.symbol.provider_symbol,
                        tick.price,
                        None,
                        tick.provider_time,
                        tick.received_at,
                    )
                )
            )
        for timeframe in self._candle_interests.get(tick.symbol.symbol, set()):
            for event in self._builder.apply_tick(tick, timeframe):
                self._put_event(event)

    def _normalize_tick(self, payload: object) -> PriceTick | None:
        if not isinstance(payload, dict):
            return None
        event_type = payload.get("event")
        if event_type is not None and event_type not in {"price", "quote"}:
            return None
        symbol_value = payload.get("symbol")
        if not isinstance(symbol_value, str):
            return None
        provider_symbol = symbol_value.upper()
        symbol = self._symbols_by_provider_symbol.get(provider_symbol)
        if symbol is None:
            return None
        price = _parse_decimal(payload.get("price"), positive=True)
        if price is None:
            return None
        provider_time = _parse_provider_time(payload.get("timestamp") or payload.get("datetime"))
        return PriceTick(symbol, price, provider_time, datetime.now(UTC))

    def _symbol_for_interest(self, interest: StreamInterest) -> SupportedSymbol | None:
        if isinstance(interest, QuoteInterest):
            for symbol in self._symbols_by_provider_symbol.values():
                if symbol.symbol == interest.symbol:
                    return symbol
            return None
        for symbol in self._symbols_by_provider_symbol.values():
            if symbol.symbol == interest.symbol:
                return symbol
        return None

    def _active_interests(self) -> tuple[StreamInterest, ...]:
        interests: list[StreamInterest] = list(self._quote_interests)
        for symbol, timeframes in self._candle_interests.items():
            interests.extend(CandleInterest(symbol, timeframe) for timeframe in timeframes)
        return tuple(interests)

    def _require_websocket(self) -> TwelveDataWebSocket:
        if self._websocket is None:
            raise ProviderUnavailableError
        return self._websocket

    def _put_event(self, event: ProviderStreamEvent) -> None:
        try:
            self.events.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("twelvedata_stream_event_dropped")

    def _put_signal(self, signal: ProviderSignal) -> None:
        self._put_event(signal)


def build_twelvedata_market_data_stream_provider(
    api_key: str | None,
    *,
    queue_capacity: int,
    heartbeat_seconds: float,
) -> TwelveDataMarketDataStreamProvider:
    if api_key is None or not api_key.strip():
        return TwelveDataMarketDataStreamProvider(
            lambda _: _MissingTwelveDataClient(),
            queue_capacity=queue_capacity,
            heartbeat_seconds=heartbeat_seconds,
        )

    def factory(on_event: Callable[[object], None]) -> TwelveDataStreamClient:
        del on_event
        return cast(TwelveDataStreamClient, TDClient(apikey=api_key))

    return TwelveDataMarketDataStreamProvider(
        factory,
        queue_capacity=queue_capacity,
        heartbeat_seconds=heartbeat_seconds,
    )


class _MissingTwelveDataClient:
    def websocket(self, **defaults: object) -> TwelveDataWebSocket:
        del defaults
        raise ProviderUnavailableError


def _bucket_open(value: datetime, duration: timedelta) -> datetime:
    utc_value = value.astimezone(UTC)
    elapsed = utc_value - EPOCH
    return EPOCH + (elapsed // duration) * duration


def _parse_decimal(value: object, *, positive: bool) -> Decimal | None:
    if not isinstance(value, str | int | float):
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    if not parsed.is_finite() or parsed < 0 or (positive and parsed <= 0):
        return None
    return parsed


def _parse_provider_time(value: object) -> datetime | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp, tz=UTC)
        except OSError, OverflowError, ValueError:
            return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return None
    return None
