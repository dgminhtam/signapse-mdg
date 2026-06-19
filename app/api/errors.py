from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.domain.errors import QuoteRequestError


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


async def database_unavailable_handler(
    _request: Request,
    _exc: Exception,
) -> JSONResponse:
    response = ErrorResponse(
        error=ErrorDetail(
            code="DATABASE_UNAVAILABLE",
            message="The symbol registry is temporarily unavailable.",
        )
    )
    return JSONResponse(status_code=503, content=response.model_dump(mode="json"))


async def quote_request_error_handler(
    _request: Request,
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
    return JSONResponse(status_code=400, content=response.model_dump(mode="json"))
