import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from app.cache.quote_cache import QuoteCache
from app.core.observability import log_event, log_failure, log_rate_limited_warning
from app.domain.errors import ProviderUnavailableError, StreamRequestError
from app.domain.streams import (
    DownstreamEvent,
    MarketStreamProvider,
    ProviderSignal,
    QuoteInterest,
    StatusEvent,
    StreamInterest,
    StreamQuote,
    StreamRequest,
)
from app.domain.symbols import SupportedSymbol
from app.services.quotes import parse_symbols

logger = logging.getLogger(__name__)


def parse_stream_request(
    raw_symbols: str | None,
    raw_timeframe: str | None,
    max_symbols: int,
    provider: str | None = None,
) -> StreamRequest:
    if raw_timeframe is not None:
        raise StreamRequestError(
            "TIMEFRAME_NOT_ALLOWED",
            "The timeframe query parameter is not allowed on the quote stream.",
        )
    try:
        symbols = parse_symbols(raw_symbols, max_symbols)
    except Exception as exc:
        code = getattr(exc, "code", "INVALID_SYMBOLS")
        message = getattr(exc, "message", "The symbols query parameter is invalid.")
        raise StreamRequestError(code, message) from exc
    return StreamRequest(tuple(symbols), provider)


@dataclass(slots=True)
class ClientRegistration:
    id: str
    request: StreamRequest
    interests: tuple[StreamInterest, ...]
    price_display_decimals: dict[str, int]
    queue: asyncio.Queue[DownstreamEvent]
    closed: asyncio.Event = field(default_factory=asyncio.Event)
    close_code: int = 1000
    close_reason: str = ""
    state: str = "CONNECTING"
    last_event_at: datetime | None = None


@dataclass(slots=True)
class InterestState:
    symbol: SupportedSymbol
    subscribers: set[str] = field(default_factory=set)
    last_event_at: datetime | None = None
    cleanup_task: asyncio.Task[None] | None = None


class StreamManager:
    def __init__(
        self,
        *,
        provider: MarketStreamProvider,
        quote_cache: QuoteCache,
        client_queue_capacity: int,
        idle_grace_seconds: float,
        stale_after_seconds: float,
        freshness_check_seconds: float,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._provider = provider
        self._quote_cache = quote_cache
        self._client_queue_capacity = client_queue_capacity
        self._idle_grace_seconds = idle_grace_seconds
        self._stale_after_seconds = stale_after_seconds
        self._freshness_check_seconds = freshness_check_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._clients: dict[str, ClientRegistration] = {}
        self._interests: dict[StreamInterest, InterestState] = {}
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
            asyncio.create_task(self._monitor_freshness(), name="stream-freshness-monitor"),
        ]

    async def register(
        self,
        request: StreamRequest,
        symbols: list[SupportedSymbol],
    ) -> ClientRegistration:
        if self._stopping:
            error = ProviderUnavailableError(
                failure_reason="REQUEST_FAILED",
                retryable=True,
                operation="stream.register",
            )
            log_failure(logger, "stream_register_unavailable", error)
            raise error
        await self.start()
        symbols_by_name = {symbol.symbol: symbol for symbol in symbols}
        interests = tuple(
            QuoteInterest(
                name,
                symbols_by_name[name].provider,
                symbols_by_name[name].provider_symbol,
            )
            for name in request.symbols
        )
        registration = ClientRegistration(
            id=uuid4().hex,
            request=request,
            interests=interests,
            price_display_decimals={
                name: symbols_by_name[name].price_display_decimals for name in request.symbols
            },
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
                        await self._open_interest(symbol)
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
        log_event(
            logger,
            logging.INFO,
            "stream_client_registered",
            operation="stream.register",
            client_id=registration.id,
            symbols=request.symbols,
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
        log_event(
            logger,
            logging.INFO,
            "stream_client_unregistered",
            operation="stream.unregister",
            client_id=client_id,
        )

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

    async def _open_interest(self, symbol: SupportedSymbol) -> None:
        await self._provider.subscribe_quote(symbol)

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
                elif isinstance(event, ProviderSignal):
                    await self._handle_signal(event)
            finally:
                events.task_done()

    async def _handle_quote(self, event: StreamQuote) -> None:
        await self._quote_cache.put_many([event.quote])
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
            state.last_event_at = now
            client_ids = tuple(state.subscribers)
            registrations = [
                self._clients[client_id] for client_id in client_ids if client_id in self._clients
            ]
            for registration in registrations:
                registration.last_event_at = now
        for registration in registrations:
            self._enqueue(registration, event)
            if registration.state != "SUBSCRIBED":
                registration.state = "SUBSCRIBED"
                self._enqueue_status(registration, "SUBSCRIBED")

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
                registration.state = "RECONNECTING"
                self._enqueue_status(registration, "RECONNECTING", affected=list(signal.interests))
                continue
            registration.state = "ERROR"
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

    def _update_registration_state(self, registration: ClientRegistration, now: datetime) -> None:
        if registration.last_event_at is None:
            return
        age = (now - registration.last_event_at).total_seconds()
        if age > self._stale_after_seconds and registration.state != "STALE":
            registration.state = "STALE"
            self._enqueue_status(registration, "STALE")

    async def _monitor_freshness(self) -> None:
        while True:
            await asyncio.sleep(self._freshness_check_seconds)
            now = self._clock()
            async with self._lock:
                registrations = list(self._clients.values())
            for registration in registrations:
                self._update_registration_state(registration, now)

    def _enqueue_status(
        self,
        registration: ClientRegistration,
        state: str,
        *,
        affected: list[StreamInterest] | None = None,
        code: str | None = None,
        message: str | None = None,
    ) -> None:
        if affected:
            affected_symbols = {interest.symbol for interest in affected}
            symbols = tuple(
                symbol for symbol in registration.request.symbols if symbol in affected_symbols
            )
        else:
            symbols = registration.request.symbols
        self._enqueue(
            registration,
            StatusEvent(
                state=state,  # type: ignore[arg-type]
                symbols=symbols,
                channels=("quote",),
                observed_at=self._clock(),
                code=code,
                message=message,
            ),
        )

    def _enqueue(self, registration: ClientRegistration, event: DownstreamEvent) -> None:
        if registration.closed.is_set():
            return
        try:
            registration.queue.put_nowait(event)
        except asyncio.QueueFull:
            registration.close_code = 1013
            registration.close_reason = "CLIENT_TOO_SLOW"
            registration.closed.set()
            log_rate_limited_warning(
                logger,
                "stream_client_queue_full",
                key=f"client:{registration.id}:queue_full",
                client_id=registration.id,
            )
