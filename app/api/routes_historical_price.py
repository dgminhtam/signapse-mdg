from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

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
from app.api.routes_candles import get_candle_service
from app.api.serialization import format_datetime, format_price
from app.domain.errors import CandleRequestError, ProviderSelectionError
from app.services.candles import CandleService
from app.services.historical_prices import (
    HistoricalPriceResult,
    HistoricalPriceService,
    parse_historical_price_request,
)
from app.services.provider_selection import parse_provider_values

router = APIRouter(prefix="/v1", tags=["historical-price"])


class HistoricalPriceResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    symbol: str
    price: DecimalString = Field(description=PRICE_DESCRIPTION)
    priced_at: UtcTimestamp = Field(
        description="Selected completed candle open time, possibly earlier than at."
    )
    resolution: str = Field(json_schema_extra={"enum": ["1m", "5m", "1h", "1d"]})


def get_historical_price_service(
    candle_service: Annotated[CandleService, Depends(get_candle_service)],
) -> HistoricalPriceService:
    return HistoricalPriceService(candle_service)


@router.get(
    "/historical-price",
    response_model=HistoricalPriceResponse,
    summary="Resolve a historical price at or before an instant",
    description="Tries resolutions 1m, 5m, 1h then 1d, scanning two eligible slots backward per "
    "resolution. Selects the latest completed candle in the first successful resolution with "
    "closeTime <= at; returns its close price and open time as pricedAt. Natural/retention gaps "
    "and closed sessions may use a coarser resolution, but operational failure returns 503. "
    "Every attempt uses the same selected provider; no resampling or cross-provider fallback. "
    "Future at values return 400. No eligible candle after all resolutions returns 404. "
    "There is no public timeframe selector. " + RAW_QUERY_DESCRIPTION,
    openapi_extra={
        "parameters": [
            SYMBOL_PARAMETER,
            query_parameter(
                "at",
                "Requested non-future instant. " + UTC_QUERY_DESCRIPTION,
                UTC_QUERY_SCHEMA,
                required=True,
                example="2026-06-19T10:30:12Z",
            ),
            PROVIDER_PARAMETER,
        ]
    },
    responses={
        200: {
            "description": "Completed candle close at the selected resolution.",
            "content": {
                "application/json": {
                    "example": {
                        "symbol": "BTC/USD",
                        "price": "104250.12",
                        "pricedAt": "2026-06-19T10:29:00Z",
                        "resolution": "1m",
                    }
                }
            },
        },
        400: error_response(
            "UNSUPPORTED_SYMBOL, INVALID_PROVIDER, UNSUPPORTED_PROVIDER or "
            "INVALID_TIME_RANGE (missing, invalid, non-UTC or future at).",
            "INVALID_TIME_RANGE",
            "The candle time range is invalid.",
        ),
        404: error_response(
            "PRICE_NOT_FOUND: no eligible completed candle in any supported resolution.",
            "PRICE_NOT_FOUND",
            "No historical price is available for the requested instant.",
        ),
        503: MARKET_DATA_UNAVAILABLE_RESPONSE,
    },
)
async def get_historical_price(
    request: Request,
    service: Annotated[HistoricalPriceService, Depends(get_historical_price_service)],
) -> HistoricalPriceResponse:
    try:
        provider = parse_provider_values(request.query_params.getlist("provider"))
    except ProviderSelectionError as exc:
        raise CandleRequestError(exc.code, exc.message) from exc
    historical_price_request = parse_historical_price_request(
        request.query_params.get("symbol"),
        request.query_params.get("at"),
        provider,
    )
    result = await service.get_historical_price(historical_price_request)
    return _to_response(result)


def _to_response(result: HistoricalPriceResult) -> HistoricalPriceResponse:
    return HistoricalPriceResponse(
        symbol=result.symbol,
        price=format_price(result.price, result.price_display_decimals),
        priced_at=format_datetime(result.priced_at),
        resolution=result.resolution,
    )
