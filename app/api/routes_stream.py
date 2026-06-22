import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.serialization import format_datetime, format_decimal
from app.core.config import get_settings
from app.db.repositories import PostgresSymbolRepository
from app.db.session import build_session_factory
from app.domain.errors import DatabaseUnavailableError, ProviderUnavailableError, StreamRequestError
from app.domain.streams import (
    DownstreamEvent,
    StatusEvent,
    StreamCandle,
    StreamQuote,
)
from app.domain.symbols import SupportedSymbol
from app.services.stream_manager import ClientRegistration, StreamManager, parse_stream_request

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
    except DatabaseUnavailableError:
        raise
    except Exception as exc:
        raise DatabaseUnavailableError from exc


@router.websocket("/stream")
async def stream_market_data(websocket: WebSocket) -> None:
    await websocket.accept()
    settings = get_settings()
    try:
        request = parse_stream_request(
            websocket.query_params.get("symbols"),
            websocket.query_params.get("timeframe"),
            settings.max_quote_symbols,
        )
    except StreamRequestError as exc:
        await websocket.close(code=1008, reason=exc.code)
        return

    try:
        registry = await resolve_stream_symbols(websocket)
    except DatabaseUnavailableError:
        await websocket.close(code=1011, reason="DATABASE_UNAVAILABLE")
        return
    registry_by_symbol = {
        item.symbol: item
        for item in registry
        if hasattr(item, "symbol") and hasattr(item, "enabled") and item.enabled
    }
    if any(symbol not in registry_by_symbol for symbol in request.symbols):
        await websocket.close(code=1008, reason="UNSUPPORTED_SYMBOL")
        return

    manager = get_stream_manager(websocket)
    try:
        registration = await manager.register(
            request,
            [registry_by_symbol[symbol] for symbol in request.symbols],
        )
    except ProviderUnavailableError:
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
                await websocket.send_json(stream_event_payload(event))
    except WebSocketDisconnect:
        registration.closed.set()


def stream_event_payload(event: DownstreamEvent) -> dict[str, Any]:
    if isinstance(event, StreamQuote):
        return {
            "type": "quote",
            "symbol": event.quote.symbol,
            "price": format_decimal(event.quote.price),
            "receivedAt": format_datetime(event.quote.received_at),
        }
    if isinstance(event, StreamCandle):
        candle = event.candle
        return {
            "type": "candle",
            "symbol": candle.symbol,
            "timeframe": candle.timeframe,
            "openTime": format_datetime(candle.open_time),
            "closeTime": format_datetime(candle.close_time),
            "open": format_decimal(candle.open),
            "high": format_decimal(candle.high),
            "low": format_decimal(candle.low),
            "close": format_decimal(candle.close),
            "volume": format_decimal(candle.volume),
            "complete": candle.complete,
            "receivedAt": format_datetime(event.received_at),
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
