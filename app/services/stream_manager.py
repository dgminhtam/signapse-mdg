import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.cache.candle_cache import CandleCache
from app.cache.quote_cache import QuoteCache
from app.domain.candles import CandleRepository
from app.domain.errors import ProviderUnavailableError, StreamRequestError
from app.domain.market_sessions import get_market_session_policy
from app.domain.streams import (
    CandleInterest,
    DownstreamEvent,
    MarketStreamProvider,
    ProviderSignal,
    QuoteInterest,
    StatusEvent,
    StreamCandle,
    StreamInterest,
    StreamQuote,
    StreamRequest,
)
from app.domain.symbols import SupportedSymbol
from app.domain.timeframes import EPOCH, get_timeframe
from app.services.quotes import parse_symbols

logger = logging.getLogger(__name__)


def parse_stream_request(
    raw_symbols: str | None,
    raw_timeframe: str | None,
    max_symbols: int,
) -> StreamRequest:
    try:
        symbols = parse_symbols(raw_symbols, max_symbols)
    except Exception as exc:
        code = getattr(exc, "code", "INVALID_SYMBOLS")
        message = getattr(exc, "message", "The symbols query parameter is invalid.")
        raise StreamRequestError(code, message) from exc
    timeframe = (raw_timeframe or "").strip()
    timeframe_model = get_timeframe(timeframe)
    if timeframe_model is None or not _is_stream_timeframe(timeframe_model.value):
        raise StreamRequestError(
            "UNSUPPORTED_TIMEFRAME",
            "Timeframe is not supported by this gateway.",
        )
    return StreamRequest(tuple(symbols), timeframe)


@dataclass(slots=True)
class ClientRegistration:
    id: str
    request: StreamRequest
    interests: tuple[StreamInterest, ...]
    queue: asyncio.Queue[DownstreamEvent]
    closed: asyncio.Event = field(default_factory=asyncio.Event)
    close_code: int = 1000
    close_reason: str = ""
    state: str = "CONNECTING"


@dataclass(slots=True)
class InterestState:
    symbol: SupportedSymbol
    subscribers: set[str] = field(default_factory=set)
    last_event_at: datetime | None = None
    cleanup_task: asyncio.Task[None] | None = None
    market_closed: bool = False


class StreamManager:
    def __init__(
        self,
        *,
        provider: MarketStreamProvider,
        quote_cache: QuoteCache,
        candle_cache: CandleCache,
        candle_repository: CandleRepository | None,
        client_queue_capacity: int,
        persistence_queue_capacity: int,
        idle_grace_seconds: float,
        stale_after_seconds: float,
        freshness_check_seconds: float,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._provider = provider
        self._quote_cache = quote_cache
        self._candle_cache = candle_cache
        self._candle_repository = candle_repository
        self._client_queue_capacity = client_queue_capacity
        self._idle_grace_seconds = idle_grace_seconds
        self._stale_after_seconds = stale_after_seconds
        self._freshness_check_seconds = freshness_check_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._clients: dict[str, ClientRegistration] = {}
        self._interests: dict[StreamInterest, InterestState] = {}
        self._persistence_queue: asyncio.Queue[StreamCandle] = asyncio.Queue(
            persistence_queue_capacity
        )
        self._tasks: list[asyncio.Task[None]] = []
        self._lock = asyncio.Lock()
        self._started = False
        self._stopping = False

    @property
    def active_clients(self) -> int:
        return len(self._clients)

    @property
    def active_interests(self) -> int:
        return len(self._interests)

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._tasks = [
            asyncio.create_task(self._consume_provider(), name="stream-provider-consumer"),
            asyncio.create_task(self._persist_candles(), name="stream-candle-persistence"),
            asyncio.create_task(self._monitor_freshness(), name="stream-freshness-monitor"),
        ]

    async def register(
        self,
        request: StreamRequest,
        symbols: list[SupportedSymbol],
    ) -> ClientRegistration:
        if self._stopping:
            raise ProviderUnavailableError
        await self.start()
        symbols_by_name = {symbol.symbol: symbol for symbol in symbols}
        interests: list[StreamInterest] = []
        for name in request.symbols:
            interests.extend((QuoteInterest(name), CandleInterest(name, request.timeframe)))
        registration = ClientRegistration(
            id=uuid4().hex,
            request=request,
            interests=tuple(interests),
            queue=asyncio.Queue(self._client_queue_capacity),
        )
        opened: list[StreamInterest] = []
        async with self._lock:
            try:
                for interest in registration.interests:
                    symbol = symbols_by_name[interest.symbol]
                    state = self._interests.get(interest)
                    if state is None:
                        state = InterestState(symbol)
                        self._interests[interest] = state
                        await self._open_interest(interest, symbol)
                        opened.append(interest)
                    if state.cleanup_task is not None:
                        state.cleanup_task.cancel()
                        state.cleanup_task = None
                    state.subscribers.add(registration.id)
                self._clients[registration.id] = registration
            except Exception:
                for interest in opened:
                    self._interests.pop(interest, None)
                    await self._provider.unsubscribe(interest)
                raise
        self._enqueue_status(registration, "CONNECTING")
        self._update_market_session_states(self._clock())
        logger.info(
            "stream_client_registered",
            extra={"client_id": registration.id, "symbols": request.symbols},
        )
        return registration

    async def unregister(self, client_id: str) -> None:
        async with self._lock:
            registration = self._clients.pop(client_id, None)
            if registration is None:
                return
            registration.closed.set()
            for interest in registration.interests:
                state = self._interests.get(interest)
                if state is None:
                    continue
                state.subscribers.discard(client_id)
                if not state.subscribers and state.cleanup_task is None:
                    state.cleanup_task = asyncio.create_task(
                        self._cleanup_interest(interest),
                        name=f"stream-idle-cleanup-{client_id}",
                    )
        logger.info("stream_client_unregistered", extra={"client_id": client_id})

    async def stop(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        async with self._lock:
            registrations = list(self._clients.values())
            cleanup_tasks = [
                state.cleanup_task
                for state in self._interests.values()
                if state.cleanup_task is not None
            ]
            self._clients.clear()
            self._interests.clear()
        for registration in registrations:
            registration.close_code = 1012
            registration.close_reason = "SERVICE_RESTART"
            registration.closed.set()
        for task in cleanup_tasks:
            task.cancel()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, *cleanup_tasks, return_exceptions=True)
        self._tasks.clear()
        await self._provider.close()

    async def _open_interest(
        self,
        interest: StreamInterest,
        symbol: SupportedSymbol,
    ) -> None:
        if isinstance(interest, QuoteInterest):
            await self._provider.subscribe_quote(symbol)
            return
        timeframe = get_timeframe(interest.timeframe)
        if timeframe is None:
            raise ProviderUnavailableError
        await self._provider.subscribe_candle(
            symbol,
            interest.timeframe,
            timeframe.provider_interval,
        )

    async def _cleanup_interest(self, interest: StreamInterest) -> None:
        try:
            await asyncio.sleep(self._idle_grace_seconds)
            async with self._lock:
                state = self._interests.get(interest)
                if state is None or state.subscribers:
                    return
                self._interests.pop(interest, None)
            await self._provider.unsubscribe(interest)
        except asyncio.CancelledError:
            return

    async def _consume_provider(self) -> None:
        events = self._provider.events
        if not isinstance(events, asyncio.Queue):
            raise TypeError("Stream provider events must be an asyncio.Queue")
        while True:
            event = await events.get()
            try:
                if isinstance(event, StreamQuote):
                    await self._handle_quote(event)
                elif isinstance(event, StreamCandle):
                    await self._handle_candle(event)
                elif isinstance(event, ProviderSignal):
                    await self._handle_signal(event)
            finally:
                events.task_done()

    async def _handle_quote(self, event: StreamQuote) -> None:
        await self._quote_cache.put_many([event.quote])
        await self._mark_fresh_and_fanout(event.interest, event)

    async def _handle_candle(self, event: StreamCandle) -> None:
        state = self._interests.get(event.interest)
        symbol = state.symbol if state is not None else None
        if symbol is not None and not get_market_session_policy(symbol).is_eligible(
            event.candle.open_time,
            event.candle.timeframe,
        ):
            return
        if event.candle.complete:
            await self._candle_cache.remove(
                event.candle.symbol,
                event.candle.timeframe,
                open_time=event.candle.open_time,
            )
            try:
                self._persistence_queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.error(
                    "stream_candle_persistence_queue_full",
                    extra={"symbol": event.candle.symbol},
                )
        else:
            await self._candle_cache.put(event.candle)
        await self._mark_fresh_and_fanout(event.interest, event)

    async def _mark_fresh_and_fanout(
        self,
        interest: StreamInterest,
        event: DownstreamEvent,
    ) -> None:
        now = self._clock()
        async with self._lock:
            state = self._interests.get(interest)
            if state is None:
                return
            state.market_closed = False
            state.last_event_at = now
            client_ids = tuple(state.subscribers)
            registrations = [
                self._clients[client_id] for client_id in client_ids if client_id in self._clients
            ]
        for registration in registrations:
            self._enqueue(registration, event)
            self._update_registration_state(registration, now)

    async def _handle_signal(self, signal: ProviderSignal) -> None:
        async with self._lock:
            client_ids = {
                client_id
                for interest in signal.interests
                if (state := self._interests.get(interest)) is not None
                for client_id in state.subscribers
            }
            registrations = [
                self._clients[client_id] for client_id in client_ids if client_id in self._clients
            ]
        for registration in registrations:
            if signal.state == "RECONNECTING":
                self._enqueue_status(registration, "RECONNECTING", affected=list(signal.interests))
            elif signal.state in {"MARKET_CLOSED", "CONNECTING"}:
                self._apply_signal_session_state(signal)
                self._enqueue_status(
                    registration,
                    signal.state,
                    affected=list(signal.interests),
                )
            else:
                self._enqueue_status(
                    registration,
                    "ERROR",
                    affected=list(signal.interests),
                    code=signal.code,
                    message=signal.message,
                )
                registration.close_code = 1011
                registration.close_reason = signal.code
                registration.closed.set()

    def _update_registration_state(
        self,
        registration: ClientRegistration,
        now: datetime,
    ) -> None:
        states = [self._interests.get(interest) for interest in registration.interests]
        required = [
            (interest, state)
            for interest, state in zip(registration.interests, states, strict=True)
            if state is not None and not state.market_closed
        ]
        if not required:
            return
        if any(state is None or state.last_event_at is None for _, state in required):
            return
        stale = [
            interest
            for interest, state in required
            if state is not None
            and state.last_event_at is not None
            and (now - state.last_event_at).total_seconds() > self._stale_after_seconds
        ]
        target = "STALE" if stale else "SUBSCRIBED"
        if registration.state != target:
            registration.state = target
            self._enqueue_status(registration, target, affected=stale or None)

    async def _monitor_freshness(self) -> None:
        while True:
            await asyncio.sleep(self._freshness_check_seconds)
            now = self._clock()
            async with self._lock:
                registrations = list(self._clients.values())
            self._update_market_session_states(now)
            for registration in registrations:
                self._update_registration_state(registration, now)

    def _apply_signal_session_state(self, signal: ProviderSignal) -> None:
        for interest in signal.interests:
            state = self._interests.get(interest)
            if state is None or not isinstance(interest, CandleInterest):
                continue
            if signal.state == "MARKET_CLOSED":
                state.market_closed = True
            elif signal.state == "CONNECTING":
                state.market_closed = False
                state.last_event_at = None

    def _update_market_session_states(self, now: datetime) -> None:
        for interest, state in list(self._interests.items()):
            if not isinstance(interest, CandleInterest):
                continue
            timeframe = get_timeframe(interest.timeframe)
            if timeframe is None:
                continue
            bucket_open = _bucket_open(now, timeframe.duration)
            eligible = get_market_session_policy(state.symbol).is_eligible(
                bucket_open,
                interest.timeframe,
            )
            if eligible and state.market_closed:
                state.market_closed = False
                state.last_event_at = None
                self._emit_interest_status(interest, "CONNECTING")
            elif not eligible and not state.market_closed:
                state.market_closed = True
                self._emit_interest_status(interest, "MARKET_CLOSED")

    def _emit_interest_status(self, interest: StreamInterest, state: str) -> None:
        interest_state = self._interests.get(interest)
        if interest_state is None:
            return
        for client_id in tuple(interest_state.subscribers):
            registration = self._clients.get(client_id)
            if registration is not None:
                self._enqueue_status(registration, state, affected=[interest])

    async def _persist_candles(self) -> None:
        while True:
            event = await self._persistence_queue.get()
            try:
                if self._candle_repository is not None:
                    await self._candle_repository.upsert_complete([event.candle])
            except Exception:
                logger.error(
                    "stream_candle_persistence_failed",
                    extra={"symbol": event.candle.symbol},
                )
            finally:
                self._persistence_queue.task_done()

    def _enqueue_status(
        self,
        registration: ClientRegistration,
        state: str,
        *,
        affected: list[StreamInterest] | None = None,
        code: str | None = None,
        message: str | None = None,
    ) -> None:
        interests = affected or list(registration.interests)
        requested_order = registration.request.symbols
        affected_symbols = {interest.symbol for interest in interests}
        symbols = tuple(symbol for symbol in requested_order if symbol in affected_symbols)
        channels = tuple(
            channel
            for channel in ("quote", "candle")
            if any(interest.channel == channel for interest in interests)
        )
        self._enqueue(
            registration,
            StatusEvent(
                state=state,  # type: ignore[arg-type]
                symbols=symbols,
                channels=channels,  # type: ignore[arg-type]
                observed_at=self._clock(),
                code=code,
                message=message,
            ),
        )

    def _enqueue(
        self,
        registration: ClientRegistration,
        event: DownstreamEvent,
    ) -> None:
        if registration.closed.is_set():
            return
        try:
            registration.queue.put_nowait(event)
        except asyncio.QueueFull:
            registration.close_code = 1013
            registration.close_reason = "CLIENT_TOO_SLOW"
            registration.closed.set()
            logger.warning(
                "stream_client_queue_full",
                extra={"client_id": registration.id},
            )


def _bucket_open(value: datetime, duration: timedelta) -> datetime:
    utc_value = value.astimezone(UTC)
    elapsed = utc_value - EPOCH
    return EPOCH + (elapsed // duration) * duration


def _is_stream_timeframe(timeframe: str) -> bool:
    return timeframe in {"1m", "5m", "15m", "1h", "1d"}
