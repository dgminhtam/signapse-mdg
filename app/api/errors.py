import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.observability import (
    REQUEST_ID_HEADER,
    current_request_id,
    failure_metadata,
    log_event,
    request_id_from_scope,
)
from app.domain.errors import (
    CandleRequestError,
    DatabaseUnavailableError,
    EconomicCalendarRequestError,
    HistoricalPriceNotFoundError,
    ProviderUnavailableError,
    QuoteRequestError,
)

logger = logging.getLogger("app.api.errors")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


def _error_response(
    status_code: int,
    response: ErrorResponse,
    request: Request | None = None,
) -> JSONResponse:
    result = JSONResponse(status_code=status_code, content=response.model_dump(mode="json"))
    request_id = current_request_id() or (
        request_id_from_scope(request.scope) if request is not None else None
    )
    if request_id is not None:
        result.headers[REQUEST_ID_HEADER] = request_id
    return result


async def database_unavailable_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, DatabaseUnavailableError):
        raise exc
    log_event(
        logger,
        logging.ERROR,
        "database_operation_failed",
        request_id=request_id_from_scope(request.scope),
        operation=exc.operation or request.url.path,
        error_code="DATABASE_UNAVAILABLE",
        **failure_metadata(exc),
    )
    response = ErrorResponse(
        error=ErrorDetail(
            code="DATABASE_UNAVAILABLE",
            message="The requested database-backed capability is temporarily unavailable.",
        )
    )
    return _error_response(503, response, request)


async def quote_request_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, QuoteRequestError):
        raise exc
    response = ErrorResponse(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
        )
    )
    return _error_response(400, response, request)


async def candle_request_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, CandleRequestError):
        raise exc
    response = ErrorResponse(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )
    )
    return _error_response(400, response, request)


async def economic_calendar_request_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, EconomicCalendarRequestError):
        raise exc
    response = ErrorResponse(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
        )
    )
    return _error_response(400, response, request)


async def historical_price_not_found_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, HistoricalPriceNotFoundError):
        raise exc
    response = ErrorResponse(
        error=ErrorDetail(
            code="PRICE_NOT_FOUND",
            message="No historical price is available for the requested instant.",
        )
    )
    return _error_response(404, response, request)


async def provider_unavailable_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, ProviderUnavailableError):
        raise exc
    log_event(
        logger,
        logging.ERROR,
        "provider_request_failed",
        request_id=request_id_from_scope(request.scope),
        operation=exc.operation or request.url.path,
        provider=exc.provider,
        provider_symbol=exc.provider_symbol,
        symbol=exc.symbol,
        timeframe=exc.timeframe,
        **failure_metadata(exc),
        error_code="PROVIDER_UNAVAILABLE",
    )
    response = ErrorResponse(
        error=ErrorDetail(
            code="PROVIDER_UNAVAILABLE",
            message="The market data provider is temporarily unavailable.",
        )
    )
    return _error_response(503, response, request)


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log_event(
        logger,
        logging.ERROR,
        "unexpected_gateway_error",
        request_id=request_id_from_scope(request.scope),
        operation=request.url.path,
        error_code="INTERNAL_ERROR",
        exception_type=type(exc).__name__,
        exc_info=True,
    )
    response = ErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_ERROR",
            message="The gateway encountered an unexpected error.",
        )
    )
    return _error_response(500, response, request)
