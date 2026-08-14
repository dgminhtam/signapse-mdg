from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.candles import CandleRequest
from app.domain.errors import CandleRequestError, HistoricalPriceNotFoundError
from app.domain.symbols import SupportedSymbol
from app.services.candles import (
    INVALID_TIME_RANGE_MESSAGE,
    UNSUPPORTED_SYMBOL_MESSAGE,
    CandleService,
)


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
        timeframe_policy: Callable[[SupportedSymbol, datetime], tuple[str, ...]] | None = None,
    ) -> None:
        self._candle_service = candle_service
        self._timeframe_policy = timeframe_policy or (lambda _symbol, _at: ("1m",))

    async def get_historical_price(
        self,
        request: HistoricalPriceRequest,
    ) -> HistoricalPriceResult:
        resolver = getattr(self._candle_service, "resolve_symbol", None)
        if not callable(resolver):
            _, end = historical_price_window(request.at)
            result = await self._candle_service.get_candles(
                CandleRequest(
                    request.symbol,
                    "1m",
                    end,
                    end,
                    limit=1,
                    count_direction="backward",
                    provider=request.provider,
                )
            )
            if not result.candles:
                raise HistoricalPriceNotFoundError
            candle = result.candles[-1]
            return HistoricalPriceResult(
                result.symbol,
                candle.close,
                candle.open_time,
                result.price_display_decimals,
            )

        selected_symbol = await resolver(request.symbol, request.provider)
        for timeframe in self._timeframe_policy(selected_symbol, request.at):
            result = await self._candle_service.get_candles(
                CandleRequest(
                    request.symbol,
                    timeframe,
                    request.at,
                    request.at,
                    limit=2,
                    count_direction="backward",
                    provider=request.provider,
                ),
                resolved_symbol=selected_symbol,
            )
            eligible = [
                candle
                for candle in result.candles
                if candle.complete and candle.close_time <= request.at
            ]
            if eligible:
                candle = max(eligible, key=lambda value: value.open_time)
                return HistoricalPriceResult(
                    result.symbol,
                    candle.close,
                    candle.open_time,
                    result.price_display_decimals,
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
