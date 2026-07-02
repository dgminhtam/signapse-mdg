from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.serialization import format_datetime
from app.db.repositories import PostgresEconomicCalendarRepository
from app.db.session import get_session_factory
from app.domain.economic_calendar import EconomicCalendarRepository, EconomicCalendarResult
from app.services.economic_calendar import EconomicCalendarService, parse_economic_calendar_request

router = APIRouter(prefix="/v1", tags=["economic-calendar"])


class EconomicCalendarEventResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    key: str
    type: str
    name: str
    currency: str | None
    impact: str | None
    scheduled_at: str
    actual: str | None
    forecast: str | None
    previous: str | None
    revision: str | None
    actual_better_worse: str | None
    revision_better_worse: str | None
    first_seen_at: str
    last_seen_at: str
    last_changed_at: str


class EconomicCalendarResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    from_: str = Field(alias="from")
    to: str
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


@router.get("/economic-calendar", response_model=EconomicCalendarResponse)
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
                    first_seen_at=format_datetime(event.first_seen_at),
                    last_seen_at=format_datetime(event.last_seen_at),
                    last_changed_at=format_datetime(event.last_changed_at),
                )
                for event in result.events
            ],
        }
    )
