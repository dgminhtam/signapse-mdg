from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.candles import Candle, CandleRequest, CandleResult
from app.domain.errors import (
    CandleRequestError,
    HistoricalPriceNotFoundError,
    ProviderUnavailableError,
)
from app.services.historical_prices import (
    HISTORICAL_PRICE_RESOLUTIONS,
    HistoricalPriceRequest,
    HistoricalPriceService,
    historical_price_window,
    parse_historical_price_request,
)

START = datetime(2026, 6, 19, 10, 30, tzinfo=UTC)
AT = START + timedelta(minutes=2, seconds=12)


class StubCandleService:
    def __init__(
        self,
        results: dict[str, CandleResult | Exception],
        *,
        selected_symbol: object = object(),
    ) -> None:
        self.results = results
        self.selected_symbol = selected_symbol
        self.requests: list[CandleRequest] = []
        self.resolution_provider: str | None = None

    async def resolve_symbol(self, symbol: str, provider: str | None = None) -> object:
        assert symbol == "BTC/USD"
        self.resolution_provider = provider
        return self.selected_symbol

    async def get_candles(
        self,
        request: CandleRequest,
        *,
        resolved_symbol: object,
    ) -> CandleResult:
        assert resolved_symbol is self.selected_symbol
        self.requests.append(request)
        result = self.results.get(request.timeframe)
        if result is None:
            return result_for(request.timeframe)
        if isinstance(result, Exception):
            raise result
        return result


def result_for(timeframe: str, *candles: Candle) -> CandleResult:
    return CandleResult(
        "BTC/USD",
        timeframe,
        START,
        AT,
        list(candles),
        2,
    )


def make_candle(
    timeframe: str,
    open_time: datetime,
    close: str = "104250.12",
    *,
    complete: bool = True,
    close_time: datetime | None = None,
) -> Candle:
    durations = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "1h": timedelta(hours=1),
        "1d": timedelta(days=1),
    }
    effective_close_time = close_time or (
        open_time + durations[timeframe] - timedelta(milliseconds=1)
    )
    return Candle(
        "BTC/USD",
        "CRYPTO",
        "TWELVE_DATA",
        "BTC/USD",
        timeframe,
        open_time,
        effective_close_time,
        Decimal("104000"),
        Decimal("104300"),
        Decimal("103900"),
        Decimal(close),
        Decimal("12.34"),
        complete,
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


async def test_historical_price_service_returns_finest_completed_candle() -> None:
    candle = make_candle("1m", START)
    service_stub = StubCandleService({"1m": result_for("1m", candle)})
    service = HistoricalPriceService(service_stub, clock=lambda: AT)  # type: ignore[arg-type]

    result = await service.get_historical_price(HistoricalPriceRequest("BTC/USD", AT))

    assert [request.timeframe for request in service_stub.requests] == ["1m"]
    assert result.symbol == "BTC/USD"
    assert result.price == Decimal("104250.12")
    assert result.priced_at == START
    assert result.resolution == "1m"
    assert result.price_display_decimals == 2


async def test_historical_price_service_falls_back_in_fixed_order() -> None:
    candle = make_candle("1h", START - timedelta(hours=1), "103500.00")
    service_stub = StubCandleService({"1h": result_for("1h", candle)})
    service = HistoricalPriceService(service_stub, clock=lambda: AT)  # type: ignore[arg-type]

    result = await service.get_historical_price(HistoricalPriceRequest("BTC/USD", AT))

    assert [request.timeframe for request in service_stub.requests] == ["1m", "5m", "1h"]
    assert result.price == Decimal("103500.00")
    assert result.priced_at == START - timedelta(hours=1)
    assert result.resolution == "1h"


async def test_historical_price_service_excludes_lookahead_and_forming_candles() -> None:
    lookahead = make_candle(
        "5m",
        START + timedelta(minutes=2),
        close_time=AT + timedelta(minutes=1),
    )
    forming = make_candle("1m", START + timedelta(minutes=1), complete=False)
    previous = make_candle("1h", START - timedelta(hours=1), "103500.00")
    service_stub = StubCandleService(
        {
            "1m": result_for("1m", forming),
            "5m": result_for("5m", lookahead),
            "1h": result_for("1h", previous),
        }
    )
    service = HistoricalPriceService(service_stub, clock=lambda: AT)  # type: ignore[arg-type]

    result = await service.get_historical_price(HistoricalPriceRequest("BTC/USD", AT))

    assert result.resolution == "1h"
    assert result.priced_at == START - timedelta(hours=1)
    assert [request.timeframe for request in service_stub.requests] == ["1m", "5m", "1h"]


async def test_historical_price_service_tries_all_four_resolutions_then_not_found() -> None:
    service_stub = StubCandleService({})
    service = HistoricalPriceService(service_stub, clock=lambda: AT)  # type: ignore[arg-type]

    with pytest.raises(HistoricalPriceNotFoundError):
        await service.get_historical_price(HistoricalPriceRequest("BTC/USD", AT))

    assert [request.timeframe for request in service_stub.requests] == list(
        HISTORICAL_PRICE_RESOLUTIONS
    )


async def test_historical_price_service_preserves_provider_selection_across_attempts() -> None:
    candle = make_candle("5m", START - timedelta(minutes=5), "103500.00")
    service_stub = StubCandleService({"5m": result_for("5m", candle)})
    service = HistoricalPriceService(service_stub, clock=lambda: AT)  # type: ignore[arg-type]

    result = await service.get_historical_price(
        HistoricalPriceRequest("BTC/USD", AT, provider="YFINANCE")
    )

    assert result.resolution == "5m"
    assert service_stub.resolution_provider == "YFINANCE"
    assert all(request.provider == "YFINANCE" for request in service_stub.requests)


async def test_historical_price_service_stops_on_provider_failure() -> None:
    service_stub = StubCandleService({"1m": ProviderUnavailableError("timeout")})
    service = HistoricalPriceService(service_stub, clock=lambda: AT)  # type: ignore[arg-type]

    with pytest.raises(ProviderUnavailableError):
        await service.get_historical_price(HistoricalPriceRequest("BTC/USD", AT))

    assert [request.timeframe for request in service_stub.requests] == ["1m"]


async def test_historical_price_service_rejects_future_before_provider_selection() -> None:
    service_stub = StubCandleService({})
    service = HistoricalPriceService(service_stub, clock=lambda: START)

    with pytest.raises(CandleRequestError) as exc_info:
        await service.get_historical_price(
            HistoricalPriceRequest("BTC/USD", START + timedelta(seconds=1))
        )

    assert exc_info.value.code == "INVALID_TIME_RANGE"
    assert service_stub.resolution_provider is None
    assert service_stub.requests == []
