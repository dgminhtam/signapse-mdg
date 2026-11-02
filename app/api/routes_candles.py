from collections.abc import Callable
from datetime import datetime
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.mt5_dependency import get_mt5_provider
from app.api.openapi import (
    MARKET_DATA_UNAVAILABLE_RESPONSE,
    PRICE_DESCRIPTION,
    PROVIDER_PARAMETER,
    RAW_QUERY_DESCRIPTION,
    SYMBOL_PARAMETER,
    UTC_QUERY_DESCRIPTION,
    UTC_QUERY_SCHEMA,
    DecimalString,
    UtcTimestamp,
    error_response,
    query_parameter,
)
from app.api.serialization import format_datetime, format_decimal, format_price
from app.cache.candle_cache import CandleCache
from app.core.config import Settings, get_settings
from app.core.time import utc_now
from app.db.repositories import PostgresCandleRepository
from app.db.session import get_session_factory
from app.domain.candles import CandleProvider, CandleRepository, CandleResult
from app.domain.errors import CandleRequestError, ProviderSelectionError
from app.domain.timeframes import TIMEFRAMES
from app.providers.binance_spot import build_binance_spot_candle_provider
from app.providers.mt5 import PROVIDER as MT5_PROVIDER
from app.providers.mt5 import MT5Provider
from app.providers.twelvedata_market_data import build_twelvedata_market_data_provider
from app.providers.yfinance_market_data import build_yfinance_candle_provider
from app.services.candle_provider_router import CandleProviderRouter
from app.services.candles import CandleService, parse_candle_request
from app.services.provider_selection import parse_provider_values

router = APIRouter(prefix="/v1", tags=["candles"])


class CandleResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    open_time: UtcTimestamp
    close_time: UtcTimestamp
    open: DecimalString = Field(description=PRICE_DESCRIPTION)
    high: DecimalString = Field(description=PRICE_DESCRIPTION)
    low: DecimalString = Field(description=PRICE_DESCRIPTION)
    close: DecimalString = Field(description=PRICE_DESCRIPTION)
    volume: DecimalString = Field(
        description="Unrounded fixed-point volume; zero may represent unavailable provider "
        "volume, not measured inactivity."
    )
    complete: bool = Field(
        description="Whether the candle has closed; forming snapshots are false."
    )


class CandleListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    symbol: str
    timeframe: str
    from_: UtcTimestamp = Field(alias="from", description="Inclusive scanned history window start.")
    to: UtcTimestamp = Field(description="Exclusive scanned history window end.")
    candles: list[CandleResponse]


@lru_cache
def get_binance_candle_provider(
    base_url: str,
    timeout_seconds: float,
) -> CandleProvider:
    return build_binance_spot_candle_provider(base_url, timeout_seconds)


@lru_cache
def get_twelvedata_candle_provider(
    api_keys: tuple[str, ...],
    base_url: str,
    timeout_seconds: float,
) -> CandleProvider:
    return build_twelvedata_market_data_provider(api_keys, base_url, timeout_seconds)


@lru_cache
def get_yfinance_candle_provider(timeout_seconds: float) -> CandleProvider:
    return build_yfinance_candle_provider(timeout_seconds)


def get_candle_provider(
    settings: Annotated[Settings, Depends(get_settings)],
    mt5: Annotated[MT5Provider | None, Depends(get_mt5_provider)] = None,
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
    twelvedata_api_keys = settings.twelvedata_effective_api_keys()
    if twelvedata_api_keys:
        providers["TWELVE_DATA"] = get_twelvedata_candle_provider(
            twelvedata_api_keys,
            settings.twelvedata_rest_base_url,
            settings.provider_http_timeout_seconds,
        )
    if mt5 is not None:
        providers[MT5_PROVIDER] = mt5
    return CandleProviderRouter(providers)


def get_candle_repository(
    session_factory: Annotated[
        async_sessionmaker[AsyncSession],
        Depends(get_session_factory),
    ],
) -> CandleRepository:
    return PostgresCandleRepository(session_factory)


@lru_cache
def _build_candle_cache(ttl_seconds: float) -> CandleCache:
    return CandleCache(ttl_seconds=ttl_seconds)


def get_candle_cache(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandleCache:
    return _build_candle_cache(settings.candle_forming_cache_ttl_seconds)


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
        count_scan_budget=settings.max_candle_count_scan_slots,
    )


def get_candle_request_clock() -> Callable[[], datetime]:
    return utc_now


@router.get(
    "/candles",
    response_model=CandleListResponse,
    summary="Get historical and forming candle snapshots",
    description="Returns candles by openTime ascending in a UTC half-open [from,to) window. "
    "Without limit/count, from is required and to defaults to one captured request-time UTC. "
    "With limit or count, use from for a forward scan, to for a backward scan, or neither for "
    "latest history. Both boundaries with limit/count, or limit with count, are invalid. "
    "limit counts eligible timeframe slots; count counts unique actual provider-backed rows. "
    "Gaps, exhausted history or the bounded internal scan budget may produce fewer rows, including "
    "an empty array. No synthetic candles, cursor or partial-result metadata are added. "
    "Response boundaries describe the window scanned. Forming candles have complete=false; "
    "completed rows win when openTime coincides. Only completed candles are persisted. "
    "Boundaries need not align to timeframe opens; provider timestamps are preserved. "
    "before is unsupported and returns 400 INVALID_TIME_RANGE. Operational failures return 503. "
    + RAW_QUERY_DESCRIPTION,
    openapi_extra={
        "parameters": [
            SYMBOL_PARAMETER,
            query_parameter(
                "timeframe",
                "Canonical timeframe, trimmed and case-sensitive.",
                {"type": "string", "enum": list(TIMEFRAMES)},
                required=True,
                example="1h",
            ),
            query_parameter(
                "from",
                "Inclusive start; required only in range mode. " + UTC_QUERY_DESCRIPTION,
                UTC_QUERY_SCHEMA,
                example="2026-06-19T00:00:00Z",
            ),
            query_parameter(
                "to",
                "Exclusive cutoff; omission uses captured request time for backward/range queries. "
                + UTC_QUERY_DESCRIPTION,
                UTC_QUERY_SCHEMA,
                example="2026-06-19T10:00:00Z",
            ),
            query_parameter(
                "limit",
                "Eligible slot count, not actual row count. Mutually exclusive with count "
                "and with both boundaries together.",
                {"type": "integer", "minimum": 1},
                example=10,
            ),
            query_parameter(
                "count",
                "Maximum actual unique snapshots including forming rows. Mutually exclusive "
                "with limit and with both boundaries together.",
                {"type": "integer", "minimum": 1},
                example=10,
            ),
            PROVIDER_PARAMETER,
        ]
    },
    responses={
        200: {
            "description": "Provider-backed candle snapshots, possibly empty.",
            "content": {
                "application/json": {
                    "example": {
                        "symbol": "BTC/USD",
                        "timeframe": "1h",
                        "from": "2026-06-19T00:00:00Z",
                        "to": "2026-06-19T01:00:00Z",
                        "candles": [],
                    }
                }
            },
        },
        400: error_response(
            "UNSUPPORTED_SYMBOL, UNSUPPORTED_TIMEFRAME, INVALID_PROVIDER, "
            "UNSUPPORTED_PROVIDER or INVALID_TIME_RANGE (invalid/missing UTC bounds, "
            "mode conflict, invalid limit/count, oversized range or any before value).",
            "INVALID_TIME_RANGE",
            "The candle time range is invalid.",
        ),
        503: MARKET_DATA_UNAVAILABLE_RESPONSE,
    },
)
async def get_candles(
    request: Request,
    service: Annotated[CandleService, Depends(get_candle_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Callable[[], datetime], Depends(get_candle_request_clock)],
) -> CandleListResponse:
    try:
        provider = parse_provider_values(request.query_params.getlist("provider"))
    except ProviderSelectionError as exc:
        raise CandleRequestError(exc.code, exc.message) from exc
    candle_request = parse_candle_request(
        request.query_params.get("symbol"),
        request.query_params.get("timeframe"),
        request.query_params.get("from"),
        request.query_params.get("to"),
        request.query_params.get("limit"),
        provider,
        raw_count=request.query_params.get("count"),
        raw_before=request.query_params.get("before"),
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
                    open=format_price(candle.open, result.price_display_decimals),
                    high=format_price(candle.high, result.price_display_decimals),
                    low=format_price(candle.low, result.price_display_decimals),
                    close=format_price(candle.close, result.price_display_decimals),
                    volume=format_decimal(candle.volume),
                    complete=candle.complete,
                )
                for candle in result.candles
            ],
        }
    )
