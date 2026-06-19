from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.time import utc_now

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["UP"]
    time: datetime


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    return HealthResponse(status="UP", time=utc_now())
