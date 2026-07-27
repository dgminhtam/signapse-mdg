from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.candles import Candle, CandleRequest, CandleResult
from app.domain.errors import CandleRequestError, HistoricalPriceNotFoundError
from app.services.historical_prices import (
    HistoricalPriceRequest,
    HistoricalPriceService,
    historical_price_window,
    parse_historical_price_request,
)

START = datetime(2026, 6, 19, 10, 30, tzinfo=UTC)


class StubCandleService:
    def __init__(self, result: CandleResult) -> None:
        self.result = result
        self.requested: CandleRequest | None = None

    async def get_candles(self, request: CandleRequest) -> CandleResult:
        self.requested = request
        return self.result


def make_candle(open_time: datetime, close: str = "104250.12") -> Candle:
    return Candle(
        "BTC/USD",
        "CRYPTO",
        "TWELVE_DATA",
        "BTC/USD",
        "1m",
        open_time,
        open_time + timedelta(minutes=1) - timedelta(milliseconds=1),
        Decimal("104000"),
        Decimal("104300"),
        Decimal("103900"),
        Decimal(close),
        Decimal("12.34"),
        True,
    )


def test_parse_historical_price_request_accepts_utc_at() -> None:
    request = parse_historical_price_request(" BTC/USD ", "2026-06-19T10:30:12Z")

    assert request == HistoricalPriceRequest(
        "BTC/USD",
        datetime(2026, 6, 19, 10, 30, 12, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("symbol", "at", "code"),
    [
        (None, "2026-06-19T10:30:12Z", "UNSUPPORTED_SYMBOL"),
        ("", "2026-06-19T10:30:12Z", "UNSUPPORTED_SYMBOL"),
        ("BTC/USD", None, "INVALID_TIME_RANGE"),
        ("BTC/USD", "", "INVALID_TIME_RANGE"),
        ("BTC/USD", "bad", "INVALID_TIME_RANGE"),
        ("BTC/USD", "2026-06-19T10:30:12+07:00", "INVALID_TIME_RANGE"),
    ],
)
def test_parse_historical_price_request_rejects_invalid_contract(
    symbol: str | None,
    at: str | None,
    code: str,
) -> None:
    with pytest.raises(CandleRequestError) as exc_info:
        parse_historical_price_request(symbol, at)

    assert exc_info.value.code == code


def test_historical_price_window_floors_to_one_minute_bucket() -> None:
    assert historical_price_window(datetime(2026, 6, 19, 10, 30, 12, 345, tzinfo=UTC)) == (
        START,
        START + timedelta(minutes=1),
    )


async def test_historical_price_service_uses_latest_one_minute_candle_lookup() -> None:
    candle = make_candle(START)
    candle_service = StubCandleService(
        CandleResult(
            "BTC/USD",
            "1m",
            START,
            START + timedelta(minutes=1),
            [candle],
            2,
        )
    )
    service = HistoricalPriceService(candle_service)  # type: ignore[arg-type]

    result = await service.get_historical_price(
        HistoricalPriceRequest("BTC/USD", START + timedelta(seconds=12))
    )

    assert candle_service.requested == CandleRequest(
        "BTC/USD",
        "1m",
        START + timedelta(minutes=1),
        START + timedelta(minutes=1),
        1,
        "backward",
    )
    assert result.symbol == "BTC/USD"
    assert result.price == Decimal("104250.12")
    assert result.priced_at == START
    assert result.price_display_decimals == 2


async def test_historical_price_service_returns_previous_available_candle() -> None:
    previous = START - timedelta(days=2, minutes=1)
    candle = make_candle(previous, "103500.00")
    candle_service = StubCandleService(
        CandleResult("BTC/USD", "1m", previous, START + timedelta(minutes=1), [candle], 2)
    )
    service = HistoricalPriceService(candle_service)  # type: ignore[arg-type]

    result = await service.get_historical_price(
        HistoricalPriceRequest("BTC/USD", START + timedelta(seconds=12))
    )

    assert result.price == Decimal("103500.00")
    assert result.priced_at == previous


async def test_historical_price_service_raises_not_found_for_empty_candles() -> None:
    service = HistoricalPriceService(
        StubCandleService(
            CandleResult("BTC/USD", "1m", START, START + timedelta(minutes=1), [], 2)
        )  # type: ignore[arg-type]
    )

    with pytest.raises(HistoricalPriceNotFoundError):
        await service.get_historical_price(HistoricalPriceRequest("BTC/USD", START))
