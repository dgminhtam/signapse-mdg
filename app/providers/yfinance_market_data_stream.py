import asyncio
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast

import yfinance  # type: ignore[import-untyped]

from app.domain.errors import ProviderUnavailableError
from app.domain.quotes import Quote
from app.domain.streams import (
    CandleInterest,
    ProviderSignal,
    ProviderStreamEvent,
    QuoteInterest,
    StreamInterest,
    StreamQuote,
)
from app.domain.symbols import SupportedSymbol
from app.domain.timeframes import get_timeframe
from app.providers.price_tick_stream import PriceTick, PriceTickCandleBuilder
from app.providers.yfinance_market_data import SUPPORTED_YFINANCE_PROVIDER_SYMBOLS

logger = logging.getLogger(__name__)


class YFinanceAsyncWebSocket(Protocol):
    async def subscribe(self, symbols: str | list[str]) -> None: ...

    async def unsubscribe(self, symbols: str | list[str]) -> None: ...

    async def listen(
        self,
        message_handler: Callable[[dict[str, object]], None] | None = None,
    ) -> None: ...

    async def close(self) -> None: ...


YFinanceStreamClientFactory = Callable[[], YFinanceAsyncWebSocket]


class YFinanceMarketDataStreamProvider:
    def __init__(
        self,
        client_factory: YFinanceStreamClientFactory,
        *,
        queue_capacity: int,
        reconnect_delay_seconds: float,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.events: asyncio.Queue[ProviderStreamEvent] = asyncio.Queue(queue_capacity)
        self._client_factory = client_factory
        self._reconnect_delay_seconds = reconnect_delay_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._client: YFinanceAsyncWebSocket | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._symbols_by_provider_symbol: dict[str, SupportedSymbol] = {}
        self._provider_symbol_refs: dict[str, int] = {}
        self._quote_interests: set[QuoteInterest] = set()
        self._candle_interests: dict[str, set[str]] = {}
        self._builder = PriceTickCandleBuilder()
        self._lock = asyncio.Lock()
        self._closing = False

    async def subscribe_quote(self, symbol: SupportedSymbol) -> None:
        if symbol.provider_symbol not in SUPPORTED_YFINANCE_PROVIDER_SYMBOLS:
            raise ProviderUnavailableError
        interest = QuoteInterest(symbol.symbol)
        async with self._lock:
            if interest in self._quote_interests:
                return
            await self._add_provider_symbol(symbol)
            self._quote_interests.add(interest)
            self._ensure_listener()

    async def subscribe_candle(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
    ) -> None:
        del provider_interval
        if symbol.provider_symbol not in SUPPORTED_YFINANCE_PROVIDER_SYMBOLS:
            raise ProviderUnavailableError
        if get_timeframe(timeframe) is None:
            raise ProviderUnavailableError
        async with self._lock:
            timeframes = self._candle_interests.setdefault(symbol.symbol, set())
            if timeframe in timeframes:
                return
            try:
                await self._add_provider_symbol(symbol)
            except BaseException:
                if not timeframes:
                    self._candle_interests.pop(symbol.symbol, None)
                raise
            timeframes.add(timeframe)
            self._ensure_listener()

    async def unsubscribe(self, interest: StreamInterest) -> None:
        task: asyncio.Task[None] | None = None
        client_to_close: YFinanceAsyncWebSocket | None = None
        async with self._lock:
            symbol = self._symbol_for_interest(interest)
            if symbol is None:
                return
            if isinstance(interest, QuoteInterest):
                if interest not in self._quote_interests:
                    return
                self._quote_interests.remove(interest)
            else:
                timeframes = self._candle_interests.get(interest.symbol)
                if timeframes is None or interest.timeframe not in timeframes:
                    return
                timeframes.remove(interest.timeframe)
                if not timeframes:
                    self._candle_interests.pop(interest.symbol, None)
            await self._remove_provider_symbol(symbol)
            if not self._provider_symbol_refs:
                task, client_to_close = self._detach_resources()
        await _cancel_task(task)
        await _close_client(client_to_close)

    async def close(self) -> None:
        async with self._lock:
            self._closing = True
            self._quote_interests.clear()
            self._candle_interests.clear()
            self._provider_symbol_refs.clear()
            self._symbols_by_provider_symbol.clear()
            task, client = self._detach_resources()
        await _cancel_task(task)
        await _close_client(client)

    async def _add_provider_symbol(self, symbol: SupportedSymbol) -> None:
        refs = self._provider_symbol_refs.get(symbol.provider_symbol, 0)
        self._provider_symbol_refs[symbol.provider_symbol] = refs + 1
        self._symbols_by_provider_symbol[symbol.provider_symbol] = symbol
        candidate: YFinanceAsyncWebSocket | None = None
        try:
            if self._client is None:
                candidate = self._client_factory()
                await candidate.subscribe(sorted(self._provider_symbol_refs))
                self._client = candidate
            elif refs == 0:
                await self._client.subscribe(symbol.provider_symbol)
        except asyncio.CancelledError:
            self._rollback_provider_symbol(symbol, refs)
            await _close_client(candidate)
            raise
        except Exception as exc:
            self._rollback_provider_symbol(symbol, refs)
            await _close_client(candidate)
            raise ProviderUnavailableError from exc

    async def _remove_provider_symbol(self, symbol: SupportedSymbol) -> None:
        refs = self._provider_symbol_refs.get(symbol.provider_symbol, 0)
        if refs > 1:
            self._provider_symbol_refs[symbol.provider_symbol] = refs - 1
            return
        self._provider_symbol_refs.pop(symbol.provider_symbol, None)
        self._symbols_by_provider_symbol.pop(symbol.provider_symbol, None)
        client = self._client
        if client is not None:
            try:
                await client.unsubscribe(symbol.provider_symbol)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning(
                    "yfinance_stream_unsubscribe_failed",
                    extra={"symbol": symbol.symbol},
                )

    def _rollback_provider_symbol(self, symbol: SupportedSymbol, previous_refs: int) -> None:
        if previous_refs == 0:
            self._provider_symbol_refs.pop(symbol.provider_symbol, None)
            self._symbols_by_provider_symbol.pop(symbol.provider_symbol, None)
        else:
            self._provider_symbol_refs[symbol.provider_symbol] = previous_refs

    def _ensure_listener(self) -> None:
        if self._listener_task is not None and not self._listener_task.done():
            return
        self._listener_task = asyncio.create_task(
            self._supervise_listener(),
            name="yfinance-market-data-stream-listener",
        )

    async def _supervise_listener(self) -> None:
        while True:
            async with self._lock:
                if self._closing or not self._provider_symbol_refs:
                    return
                client = self._client
            if client is None:
                if not await self._reconnect():
                    return
                continue
            try:
                await client.listen(self._handle_payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("yfinance_stream_listener_failed", exc_info=True)

            async with self._lock:
                if self._closing or not self._provider_symbol_refs:
                    return
                if self._client is client:
                    self._client = None
                interests = self._active_interests()
            if interests:
                self._put_event(ProviderSignal("RECONNECTING", interests, self._clock()))
            await _close_client(client)
            if self._reconnect_delay_seconds > 0:
                await asyncio.sleep(self._reconnect_delay_seconds)
            if not await self._reconnect():
                return

    async def _reconnect(self) -> bool:
        while True:
            async with self._lock:
                if self._closing or not self._provider_symbol_refs:
                    return False
                if self._client is not None:
                    return True
                symbols = sorted(self._provider_symbol_refs)
                client = self._client_factory()
                try:
                    await client.subscribe(symbols)
                except asyncio.CancelledError:
                    await _close_client(client)
                    raise
                except Exception:
                    logger.warning("yfinance_stream_reconnect_failed", exc_info=True)
                else:
                    self._client = client
                    return True
            await _close_client(client)
            if self._reconnect_delay_seconds > 0:
                await asyncio.sleep(self._reconnect_delay_seconds)

    def _handle_payload(self, payload: dict[str, object]) -> None:
        tick = self._normalize_tick(payload)
        if tick is None:
            return
        if QuoteInterest(tick.symbol.symbol) in self._quote_interests:
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
        if not isinstance(payload, Mapping):
            return None
        provider_symbol = payload.get("id")
        if not isinstance(provider_symbol, str):
            return None
        symbol = self._symbols_by_provider_symbol.get(provider_symbol)
        if symbol is None:
            return None
        price = _parse_decimal(payload.get("price"), positive=True)
        if price is None:
            return None
        provider_time, valid_time = _parse_provider_time(payload.get("time"))
        if not valid_time:
            return None
        return PriceTick(symbol, price, provider_time, self._clock())

    def _symbol_for_interest(self, interest: StreamInterest) -> SupportedSymbol | None:
        for symbol in self._symbols_by_provider_symbol.values():
            if symbol.symbol == interest.symbol:
                return symbol
        return None

    def _active_interests(self) -> tuple[StreamInterest, ...]:
        interests: list[StreamInterest] = list(self._quote_interests)
        for symbol, timeframes in self._candle_interests.items():
            interests.extend(CandleInterest(symbol, timeframe) for timeframe in timeframes)
        return tuple(interests)

    def _detach_resources(
        self,
    ) -> tuple[asyncio.Task[None] | None, YFinanceAsyncWebSocket | None]:
        task = self._listener_task
        client = self._client
        self._listener_task = None
        self._client = None
        return task, client

    def _put_event(self, event: ProviderStreamEvent) -> None:
        try:
            self.events.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("yfinance_stream_event_dropped")


def build_yfinance_market_data_stream_provider(
    *,
    queue_capacity: int,
    reconnect_delay_seconds: float,
) -> YFinanceMarketDataStreamProvider:
    def factory() -> YFinanceAsyncWebSocket:
        return cast(YFinanceAsyncWebSocket, yfinance.AsyncWebSocket(verbose=False))

    return YFinanceMarketDataStreamProvider(
        factory,
        queue_capacity=queue_capacity,
        reconnect_delay_seconds=reconnect_delay_seconds,
    )


def _parse_decimal(value: object, *, positive: bool) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, Decimal | int | float | str):
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    if not parsed.is_finite() or parsed < 0 or (positive and parsed <= 0):
        return None
    return parsed


def _parse_provider_time(value: object) -> tuple[datetime | None, bool]:
    if value is None:
        return None, True
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None, False
    try:
        timestamp = float(value)
    except ValueError:
        return None, False
    if timestamp < 0:
        return None, False
    if timestamp > 10_000_000_000:
        timestamp /= 1000
    try:
        return datetime.fromtimestamp(timestamp, tz=UTC), True
    except OSError, OverflowError, ValueError:
        return None, False


async def _cancel_task(task: asyncio.Task[None] | None) -> None:
    if task is None or task is asyncio.current_task():
        return
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def _close_client(client: YFinanceAsyncWebSocket | None) -> None:
    if client is None:
        return
    try:
        await client.close()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning("yfinance_stream_close_failed", exc_info=True)
