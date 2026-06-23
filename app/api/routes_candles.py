from collections.abc import Callable
from datetime import datetime
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.serialization import format_datetime, format_decimal
from app.cache.candle_cache import CandleCache
from app.core.config import Settings, get_settings
from app.core.time import utc_now
from app.db.repositories import PostgresCandleRepository
from app.db.session import get_session_factory
from app.domain.candles import CandleProvider, CandleRepository, CandleResult
from app.providers.binance_spot import build_binance_spot_candle_provider
from app.providers.twelvedata_market_data import build_twelvedata_market_data_provider
from app.providers.yfinance_market_data import build_yfinance_candle_provider
from app.services.candle_provider_router import CandleProviderRouter
from app.services.candles import CandleService, parse_candle_request

router = APIRouter(prefix="/v1", tags=["candles"])


class CandleResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    open_time: str
    close_time: str
    open: str
    high: str
    low: str
    close: str
    volume: str
    complete: bool


class CandleListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    symbol: str
    timeframe: str
    from_: str = Field(alias="from")
    to: str
    candles: list[CandleResponse]


@lru_cache
def get_binance_candle_provider(
    base_url: str,
    timeout_seconds: float,
) -> CandleProvider:
    return build_binance_spot_candle_provider(base_url, timeout_seconds)


@lru_cache
def get_twelvedata_candle_provider(
    api_key: str,
    base_url: str,
    timeout_seconds: float,
) -> CandleProvider:
    return build_twelvedata_market_data_provider(api_key, base_url, timeout_seconds)


@lru_cache
def get_yfinance_candle_provider(timeout_seconds: float) -> CandleProvider:
    return build_yfinance_candle_provider(timeout_seconds)


def get_candle_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandleProvider:
    providers = {
        "BINANCE_SPOT": get_binance_candle_provider(
            settings.binance_rest_base_url,
            settings.provider_http_timeout_seconds,
        ),
        "YFINANCE": get_yfinance_candle_provider(
            settings.provider_http_timeout_seconds,
        ),
    }
    if settings.twelvedata_api_key is not None and settings.twelvedata_api_key.strip():
        providers["TWELVE_DATA"] = get_twelvedata_candle_provider(
            settings.twelvedata_api_key,
            settings.twelvedata_rest_base_url,
            settings.provider_http_timeout_seconds,
        )
    return CandleProviderRouter(providers)


def get_candle_repository(
    session_factory: Annotated[
        async_sessionmaker[AsyncSession],
        Depends(get_session_factory),
    ],
) -> CandleRepository:
    return PostgresCandleRepository(session_factory)


@lru_cache
def get_candle_cache() -> CandleCache:
    return CandleCache()


def get_candle_service(
    repository: Annotated[CandleRepository, Depends(get_candle_repository)],
    provider: Annotated[CandleProvider, Depends(get_candle_provider)],
    cache: Annotated[CandleCache, Depends(get_candle_cache)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandleService:
    return CandleService(
        repository=repository,
        provider=provider,
        cache=cache,
        max_candles=settings.max_candles_per_request,
    )


def get_candle_request_clock() -> Callable[[], datetime]:
    return utc_now


@router.get("/candles", response_model=CandleListResponse)
async def get_candles(
    request: Request,
    service: Annotated[CandleService, Depends(get_candle_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Callable[[], datetime], Depends(get_candle_request_clock)],
) -> CandleListResponse:
    candle_request = parse_candle_request(
        request.query_params.get("symbol"),
        request.query_params.get("timeframe"),
        request.query_params.get("from"),
        request.query_params.get("to"),
        max_range_days=settings.max_candle_range_days,
        max_candles=settings.max_candles_per_request,
        clock=clock,
    )
    result = await service.get_candles(candle_request)
    return _to_response(result)


def _to_response(result: CandleResult) -> CandleListResponse:
    return CandleListResponse.model_validate(
        {
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "from": format_datetime(result.start),
            "to": format_datetime(result.end),
            "candles": [
                CandleResponse(
                    open_time=format_datetime(candle.open_time),
                    close_time=format_datetime(candle.close_time),
                    open=format_decimal(candle.open),
                    high=format_decimal(candle.high),
                    low=format_decimal(candle.low),
                    close=format_decimal(candle.close),
                    volume=format_decimal(candle.volume),
                    complete=candle.complete,
                )
                for candle in result.candles
            ],
        }
    )
