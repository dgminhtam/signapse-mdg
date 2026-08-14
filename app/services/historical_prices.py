from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.time import utc_now
from app.domain.candles import CandleRequest
from app.domain.errors import CandleRequestError, HistoricalPriceNotFoundError
from app.services.candles import (
    INVALID_TIME_RANGE_MESSAGE,
    UNSUPPORTED_SYMBOL_MESSAGE,
    CandleService,
)

HISTORICAL_PRICE_RESOLUTIONS = ("1m", "5m", "1h", "1d")


@dataclass(frozen=True, slots=True)
class HistoricalPriceRequest:
    symbol: str
    at: datetime
    provider: str | None = None


@dataclass(frozen=True, slots=True)
class HistoricalPriceResult:
    symbol: str
    price: Decimal
    priced_at: datetime
    price_display_decimals: int
    resolution: str = "1m"


def parse_historical_price_request(
    raw_symbol: str | None,
    raw_at: str | None,
    raw_provider: str | None = None,
) -> HistoricalPriceRequest:
    symbol = (raw_symbol or "").strip()
    if not symbol:
        raise CandleRequestError(
            "UNSUPPORTED_SYMBOL",
            UNSUPPORTED_SYMBOL_MESSAGE,
            {"symbol": symbol},
        )
    return HistoricalPriceRequest(symbol, _parse_utc(raw_at), raw_provider)


def historical_price_window(at: datetime) -> tuple[datetime, datetime]:
    priced_at = at.astimezone(UTC).replace(second=0, microsecond=0)
    return priced_at, priced_at + timedelta(minutes=1)


class HistoricalPriceService:
    def __init__(
        self,
        candle_service: CandleService,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._candle_service = candle_service
        self._clock = clock

    async def get_historical_price(
        self,
        request: HistoricalPriceRequest,
    ) -> HistoricalPriceResult:
        at = request.at.astimezone(UTC)
        if at > self._clock().astimezone(UTC):
            raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)

        resolver = getattr(self._candle_service, "resolve_symbol", None)
        selected_symbol = None
        if callable(resolver):
            selected_symbol = await resolver(request.symbol, request.provider)

        for resolution in HISTORICAL_PRICE_RESOLUTIONS:
            candle_request = CandleRequest(
                request.symbol,
                resolution,
                at,
                at,
                limit=2,
                count_direction="backward",
                provider=request.provider,
            )
            if selected_symbol is None:
                result = await self._candle_service.get_candles(candle_request)
            else:
                result = await self._candle_service.get_candles(
                    candle_request,
                    resolved_symbol=selected_symbol,
                )
            eligible = [
                candle for candle in result.candles if candle.complete and candle.close_time <= at
            ]
            if eligible:
                candle = max(eligible, key=lambda value: value.open_time)
                return HistoricalPriceResult(
                    symbol=result.symbol,
                    price=candle.close,
                    priced_at=candle.open_time,
                    price_display_decimals=result.price_display_decimals,
                    resolution=resolution,
                )

        raise HistoricalPriceNotFoundError


def _parse_utc(raw_value: str | None) -> datetime:
    if raw_value is None:
        raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
    value = raw_value.strip()
    if not value or not (value.endswith("Z") or value.endswith("+00:00")):
        raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
    return parsed.astimezone(UTC)
