from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.openapi import (
    DATABASE_UNAVAILABLE_RESPONSE,
    RAW_QUERY_DESCRIPTION,
    UTC_QUERY_DESCRIPTION,
    UTC_QUERY_SCHEMA,
    UtcTimestamp,
    error_response,
    query_parameter,
)
from app.api.serialization import format_datetime
from app.db.repositories import PostgresEconomicCalendarRepository
from app.db.session import get_session_factory
from app.domain.economic_calendar import EconomicCalendarRepository, EconomicCalendarResult
from app.services.economic_calendar import (
    ALLOWED_TYPES,
    DEFAULT_LIMIT,
    MAX_LIMIT,
    EconomicCalendarService,
    parse_economic_calendar_request,
)

router = APIRouter(prefix="/v1", tags=["economic-calendar"])


class EconomicCalendarEventResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    key: str = Field(
        description="Stable type:external_event_id identifier; MT5 suffix is mt5:occurrenceId."
    )
    type: str = Field(
        description="MT5 macro events use FOREX; other categories retain legacy data."
    )
    name: str = Field(description="Upstream event name.")
    currency: str | None = Field(description="Normalized upstream currency; null when unavailable.")
    impact: str | None = Field(description="Upstream impact label; null when unavailable.")
    scheduled_at: UtcTimestamp = Field(description="Scheduled event time in UTC.")
    actual: str | None = Field(description="Reported actual value as upstream text, nullable.")
    forecast: str | None = Field(description="Forecast value as upstream text, nullable.")
    previous: str | None = Field(description="Previous value as upstream text, nullable.")
    revision: str | None = Field(
        description="Revised previous value as text, nullable; not the MT5 revision counter."
    )
    actual_better_worse: str | None = Field(
        description="Upstream assessment of actual versus forecast, nullable."
    )
    revision_better_worse: str | None = Field(
        description="Upstream assessment of revision, nullable."
    )
    description: str | None = Field(
        description="Optional upstream event-detail enrichment; key is always emitted."
    )
    news_url: str | None = Field(
        description="Related article redirect URL or null; no article HTML is returned."
    )
    first_seen_at: UtcTimestamp = Field(description="First persistence observation time in UTC.")
    last_seen_at: UtcTimestamp = Field(description="Latest upstream observation time in UTC.")
    last_changed_at: UtcTimestamp = Field(
        description="Latest persisted content-change time in UTC."
    )


class EconomicCalendarResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    from_: UtcTimestamp = Field(alias="from")
    to: UtcTimestamp
    events: list[EconomicCalendarEventResponse]


def get_economic_calendar_repository(
    session_factory: Annotated[
        async_sessionmaker[AsyncSession],
        Depends(get_session_factory),
    ],
) -> EconomicCalendarRepository:
    return PostgresEconomicCalendarRepository(session_factory)


def get_economic_calendar_service(
    repository: Annotated[
        EconomicCalendarRepository,
        Depends(get_economic_calendar_repository),
    ],
) -> EconomicCalendarService:
    return EconomicCalendarService(repository)


@router.get(
    "/economic-calendar",
    response_model=EconomicCalendarResponse,
    summary="Read persisted economic calendar events",
    description="Reads persisted events only; does not query MT5 or trigger a refresh. "
    "Required UTC bounds satisfy from < to and select from <= scheduledAt < to. "
    "Events are ordered by scheduledAt, type and external event identifier (the suffix of key). "
    "CSV filters trim, uppercase, discard empty items and deduplicate; an explicitly empty "
    "filter is invalid. currencies and impact accept arbitrary nonempty normalized strings; "
    "unmatched values return an empty events array. All event properties are emitted; enrichment "
    "and unavailable upstream values can be null. key is type:external_event_id. Raw source HTML, "
    "internal IDs and history rows are not exposed. " + RAW_QUERY_DESCRIPTION,
    openapi_extra={
        "parameters": [
            query_parameter(
                "from",
                "Inclusive scheduledAt boundary. " + UTC_QUERY_DESCRIPTION,
                UTC_QUERY_SCHEMA,
                required=True,
                example="2026-07-01T00:00:00Z",
            ),
            query_parameter(
                "to",
                "Exclusive scheduledAt boundary. " + UTC_QUERY_DESCRIPTION,
                UTC_QUERY_SCHEMA,
                required=True,
                example="2026-07-08T00:00:00Z",
            ),
            query_parameter(
                "types",
                "CSV of allowed calendar types: "
                + ", ".join(sorted(ALLOWED_TYPES))
                + ". Case-insensitive after normalization.",
                {"type": "array", "items": {"type": "string", "enum": sorted(ALLOWED_TYPES)}},
                example=["FOREX", "METALS"],
            ),
            query_parameter(
                "currencies",
                "CSV currency filter; no fixed allowlist.",
                {"type": "array", "items": {"type": "string"}},
                example=["USD", "EUR"],
            ),
            query_parameter(
                "impact",
                "CSV impact filter; no fixed allowlist.",
                {"type": "array", "items": {"type": "string"}},
                example=["HIGH"],
            ),
            query_parameter(
                "limit",
                "Maximum events; invalid values return INVALID_LIMIT.",
                {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT, "default": DEFAULT_LIMIT},
                example=100,
            ),
        ]
    },
    responses={
        200: {
            "description": "Persisted events, possibly empty.",
            "content": {
                "application/json": {
                    "example": {
                        "from": "2026-07-01T00:00:00Z",
                        "to": "2026-07-08T00:00:00Z",
                        "events": [],
                    }
                }
            },
        },
        400: error_response(
            "INVALID_TIME_RANGE, INVALID_TYPES, INVALID_CURRENCIES, INVALID_IMPACT "
            "or INVALID_LIMIT for invalid bounds or filters.",
            "INVALID_TIME_RANGE",
            "The economic calendar time range is invalid.",
        ),
        503: DATABASE_UNAVAILABLE_RESPONSE,
    },
)
async def get_economic_calendar(
    request: Request,
    service: Annotated[EconomicCalendarService, Depends(get_economic_calendar_service)],
) -> EconomicCalendarResponse:
    calendar_request = parse_economic_calendar_request(
        request.query_params.get("from"),
        request.query_params.get("to"),
        request.query_params.get("types"),
        request.query_params.get("currencies"),
        request.query_params.get("impact"),
        request.query_params.get("limit"),
    )
    return _to_response(await service.list_events(calendar_request))


def _to_response(result: EconomicCalendarResult) -> EconomicCalendarResponse:
    return EconomicCalendarResponse.model_validate(
        {
            "from": format_datetime(result.start),
            "to": format_datetime(result.end),
            "events": [
                EconomicCalendarEventResponse(
                    key=f"{event.calendar_type}:{event.external_event_id}",
                    type=event.calendar_type,
                    name=event.name,
                    currency=event.currency,
                    impact=event.impact,
                    scheduled_at=format_datetime(event.scheduled_at),
                    actual=event.actual,
                    forecast=event.forecast,
                    previous=event.previous,
                    revision=event.revision,
                    actual_better_worse=event.actual_better_worse,
                    revision_better_worse=event.revision_better_worse,
                    description=event.description,
                    news_url=event.news_url,
                    first_seen_at=format_datetime(event.first_seen_at),
                    last_seen_at=format_datetime(event.last_seen_at),
                    last_changed_at=format_datetime(event.last_changed_at),
                )
                for event in result.events
            ],
        }
    )
