import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.serialization import format_datetime, format_price
from app.core.config import get_settings
from app.core.observability import failure_metadata, log_event, log_failure
from app.db.repositories import PostgresSymbolRepository
from app.db.session import build_session_factory
from app.domain.errors import (
    DatabaseUnavailableError,
    ProviderSelectionError,
    ProviderUnavailableError,
    StreamRequestError,
)
from app.domain.streams import (
    DownstreamEvent,
    StatusEvent,
    StreamQuote,
)
from app.domain.symbols import SupportedSymbol
from app.services.provider_selection import parse_provider_values, resolve_provider_selection
from app.services.stream_manager import ClientRegistration, StreamManager, parse_stream_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["stream"])


def get_stream_manager(websocket: WebSocket) -> StreamManager:
    manager = getattr(websocket.app.state, "stream_manager", None)
    if not isinstance(manager, StreamManager):
        raise RuntimeError("Stream manager is not initialized.")
    return manager


async def resolve_stream_symbols(websocket: WebSocket) -> list[SupportedSymbol]:
    settings = get_settings()
    database = build_session_factory(settings)
    if database is None:
        raise DatabaseUnavailableError
    _, session_factory = database
    try:
        async with session_factory() as session:
            return await PostgresSymbolRepository(session).list_enabled()
    except DatabaseUnavailableError as exc:
        log_event(
            logger,
            logging.ERROR,
            "websocket_database_unavailable",
            operation="stream.resolve_symbols",
            error_code="DATABASE_UNAVAILABLE",
            failure_reason=exc.failure_reason,
            retryable=exc.retryable,
        )
        raise
    except Exception as exc:
        metadata = failure_metadata(exc)
        log_failure(
            logger,
            "websocket_symbol_resolution_failed",
            exc,
            operation="stream.resolve_symbols",
        )
        raise DatabaseUnavailableError(
            operation="stream.resolve_symbols",
            failure_reason="DATABASE_QUERY_FAILED",
            retryable=bool(metadata["retryable"]),
        ) from exc


@router.websocket("/stream")
async def stream_market_data(websocket: WebSocket) -> None:
    await websocket.accept()
    settings = get_settings()
    raw_symbols = websocket.query_params.get("symbols")
    raw_timeframe = websocket.query_params.get("timeframe")
    try:
        # Check timeframe presence before even parsing Provider Override so every legacy
        # candle-stream URL receives the same explicit quote-only rejection.
        parse_stream_request(
            raw_symbols,
            raw_timeframe,
            settings.max_quote_symbols,
        )
        provider = parse_provider_values(
            websocket.query_params.getlist("provider"),
            error_type=StreamRequestError,
        )
        request = parse_stream_request(
            raw_symbols,
            None,
            settings.max_quote_symbols,
            provider,
        )
    except StreamRequestError as exc:
        log_event(
            logger,
            logging.WARNING,
            "websocket_request_rejected",
            operation="stream.request",
            error_code=exc.code,
            symbols=raw_symbols,
            timeframe=raw_timeframe,
        )
        await websocket.close(code=1008, reason=exc.code)
        return

    try:
        registry = await resolve_stream_symbols(websocket)
    except DatabaseUnavailableError as exc:
        log_event(
            logger,
            logging.ERROR,
            "websocket_database_unavailable",
            operation="stream.request",
            error_code="DATABASE_UNAVAILABLE",
            failure_reason=exc.failure_reason,
            retryable=exc.retryable,
        )
        await websocket.close(code=1011, reason="DATABASE_UNAVAILABLE")
        return
    registry_by_symbol = {item.symbol: item for item in registry}
    if any(symbol not in registry_by_symbol for symbol in request.symbols):
        await websocket.close(code=1008, reason="UNSUPPORTED_SYMBOL")
        return
    selected_symbols: list[SupportedSymbol] = []
    try:
        for symbol_name in request.symbols:
            selected, _selection = resolve_provider_selection(
                registry_by_symbol[symbol_name],
                request.provider,
            )
            selected_symbols.append(selected)
    except ProviderSelectionError as exc:
        log_event(
            logger,
            logging.WARNING,
            "websocket_provider_selection_rejected",
            operation="stream.provider_selection",
            error_code=exc.code,
        )
        code = exc.code
        if code == "UNSUPPORTED_PROVIDER":
            await websocket.close(code=1008, reason=code)
        else:
            await websocket.close(code=1011, reason="DATABASE_UNAVAILABLE")
        return

    manager = get_stream_manager(websocket)
    try:
        registration = await manager.register(
            request,
            selected_symbols,
        )
    except ProviderUnavailableError as exc:
        log_event(
            logger,
            logging.ERROR,
            "websocket_provider_unavailable",
            operation="stream.register",
            error_code="PROVIDER_UNAVAILABLE",
            failure_reason=exc.failure_reason,
            retryable=exc.retryable,
        )
        await websocket.close(code=1011, reason="PROVIDER_UNAVAILABLE")
        return

    sender = asyncio.create_task(
        _send_events(websocket, registration),
        name=f"stream-client-sender-{registration.id}",
    )
    try:
        while not registration.closed.is_set():
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.unregister(registration.id)
        sender.cancel()
        await asyncio.gather(sender, return_exceptions=True)


async def _send_events(
    websocket: WebSocket,
    registration: ClientRegistration,
) -> None:
    try:
        while True:
            if registration.closed.is_set() and registration.queue.empty():
                await websocket.close(
                    code=registration.close_code,
                    reason=registration.close_reason,
                )
                return
            queue_task = asyncio.create_task(registration.queue.get())
            closed_task = asyncio.create_task(registration.closed.wait())
            done, pending = await asyncio.wait(
                {queue_task, closed_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            if queue_task in done:
                event = queue_task.result()
                registration.queue.task_done()
                await websocket.send_json(
                    stream_event_payload(event, registration.price_display_decimals)
                )
    except WebSocketDisconnect:
        registration.closed.set()


def stream_event_payload(
    event: DownstreamEvent,
    price_display_decimals: dict[str, int],
) -> dict[str, Any]:
    if isinstance(event, StreamQuote):
        return {
            "type": "quote",
            "symbol": event.quote.symbol,
            "price": format_price(
                event.quote.price,
                price_display_decimals[event.quote.symbol],
            ),
            "receivedAt": format_datetime(event.quote.received_at),
        }
    if isinstance(event, StatusEvent):
        payload: dict[str, Any] = {
            "type": "status",
            "state": event.state,
            "symbols": list(event.symbols),
            "channels": list(event.channels),
            "observedAt": format_datetime(event.observed_at),
        }
        if event.state == "ERROR":
            payload["code"] = event.code
            payload["message"] = event.message
        return payload
    raise TypeError("Unsupported downstream stream event.")
