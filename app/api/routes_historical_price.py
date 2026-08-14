from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

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
    price: str
    priced_at: str


def get_historical_price_service(
    candle_service: Annotated[CandleService, Depends(get_candle_service)],
) -> HistoricalPriceService:
    return HistoricalPriceService(candle_service)


@router.get("/historical-price", response_model=HistoricalPriceResponse)
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
    )
