import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.config import get_settings
from app.core.observability import log_event, log_failure
from app.core.time import utc_now
from app.db.session import build_session_factory

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["UP"] = Field(description="The application can serve HTTP requests.")
    time: datetime = Field(description="Current gateway time in UTC.")


class ReadyResponse(BaseModel):
    status: Literal["READY", "NOT_READY"] = Field(
        description="Result of the PostgreSQL readiness probe."
    )
    time: datetime = Field(description="Probe response time in UTC.")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check HTTP liveness",
    description="Returns UP without querying PostgreSQL or market-data providers. "
    "This does not establish dependency readiness or feature acceptance.",
    responses={
        200: {
            "description": "Application is serving requests.",
            "content": {
                "application/json": {"example": {"status": "UP", "time": "2026-10-15T00:00:00Z"}}
            },
        }
    },
)
async def get_health() -> HealthResponse:
    return HealthResponse(status="UP", time=utc_now())


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Check PostgreSQL readiness",
    description="Runs SELECT 1 against the configured PostgreSQL connection. Returns 503 NOT_READY "
    "if DATABASE_URL is absent or the probe fails. It does not verify migrations, provider "
    "credentials, data freshness or upstream availability. The 503 body is a readiness result, "
    "not the error envelope used by data endpoints.",
    responses={
        200: {
            "description": "Database probe succeeded.",
            "content": {
                "application/json": {"example": {"status": "READY", "time": "2026-10-15T00:00:00Z"}}
            },
        },
        503: {
            "model": ReadyResponse,
            "description": "Database is not configured or probe failed.",
            "content": {
                "application/json": {
                    "example": {"status": "NOT_READY", "time": "2026-10-15T00:00:00Z"}
                }
            },
        },
    },
)
async def get_ready() -> ReadyResponse | JSONResponse:
    settings = get_settings()
    if settings.database_url is None:
        log_event(
            logger,
            logging.WARNING,
            "readiness_dependency_unavailable",
            operation="readiness.database_probe",
            dependency="database",
            failure_reason="DATABASE_QUERY_FAILED",
            retryable=False,
        )
        return JSONResponse(
            status_code=503,
            content=ReadyResponse(status="NOT_READY", time=utc_now()).model_dump(mode="json"),
        )

    try:
        built = build_session_factory(settings)
        if built is None:
            raise RuntimeError("database session factory is unavailable")
        _, session_factory = built
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        log_failure(
            logger,
            "readiness_database_probe_failed",
            exc,
            operation="readiness.database_probe",
            dependency="database",
        )
        return JSONResponse(
            status_code=503,
            content=ReadyResponse(status="NOT_READY", time=utc_now()).model_dump(mode="json"),
        )

    return ReadyResponse(status="READY", time=utc_now())
