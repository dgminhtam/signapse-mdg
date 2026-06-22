from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.cache.candle_cache import CandleCache
from app.domain.candle_schedules import ProviderFetchSection, get_candle_schedule
from app.domain.candles import Candle, CandleRequest
from app.domain.errors import CandleRequestError, DatabaseUnavailableError, ProviderUnavailableError
from app.domain.market_sessions import get_market_session_policy
from app.domain.symbols import SupportedSymbol
from app.domain.timeframes import get_timeframe
from app.services.candles import CandleService, _find_gaps, parse_candle_request

BTC = SupportedSymbol("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True)
EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True)
SPY = SupportedSymbol("SPY", "ETF", "TWELVE_DATA", "SPY", True)
WTI = SupportedSymbol("WTI", "COMMODITY", "TWELVE_DATA", "WTI", True)
START = datetime(2026, 6, 19, 0, 0, tzinfo=UTC)


def make_candle(
    open_time: datetime,
    *,
    symbol: SupportedSymbol = BTC,
    complete: bool = True,
    close: str = "10.5",
) -> Candle:
    return Candle(
        symbol=symbol.symbol,
        asset_class=symbol.asset_class,
        provider=symbol.provider,
        provider_symbol=symbol.provider_symbol,
        timeframe="1m",
        open_time=open_time,
        close_time=open_time + timedelta(minutes=1) - timedelta(milliseconds=1),
        open=Decimal("10"),
        high=Decimal("11"),
        low=Decimal("9"),
        close=Decimal(close),
        volume=Decimal("12.34"),
        complete=complete,
    )


class FakeRepository:
    def __init__(
        self,
        persisted: list[Candle] | None = None,
        symbol: SupportedSymbol | None = BTC,
    ) -> None:
        self.persisted = persisted or []
        self.symbol = symbol
        self.upserted: list[Candle] = []

    async def get_enabled_symbol(self, symbol: str) -> SupportedSymbol | None:
        return self.symbol if self.symbol is not None and self.symbol.symbol == symbol else None

    async def list_complete(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        del symbol, timeframe, start, end
        return self.persisted

    async def upsert_complete(self, candles: list[Candle]) -> None:
        self.upserted.extend(candles)


class FakeProvider:
    def __init__(self, candles: list[Candle] | None = None) -> None:
        self.candles = candles or []
        self.calls: list[tuple[datetime, datetime, int]] = []

    async def fetch_candles(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[Candle]:
        del symbol, timeframe, provider_interval
        self.calls.append((start, end, limit))
        return [candle for candle in self.candles if start <= candle.open_time < end]


def test_parse_candle_request_accepts_aligned_half_open_range() -> None:
    request = parse_candle_request(
        "BTC/USD",
        "1m",
        "2026-06-19T00:00:00Z",
        "2026-06-19T00:02:00Z",
        max_range_days=30,
        max_candles=1000,
    )

    assert request == CandleRequest("BTC/USD", "1m", START, START + timedelta(minutes=2))


def test_parse_candle_request_accepts_unaligned_range() -> None:
    request = parse_candle_request(
        "BTC/USD",
        "1m",
        "2026-06-19T00:00:30Z",
        "2026-06-19T00:02:15Z",
        max_range_days=30,
        max_candles=1000,
    )

    assert request.start == START + timedelta(seconds=30)
    assert request.end == START + timedelta(minutes=2, seconds=15)


def test_parse_candle_request_defaults_omitted_to_to_captured_now() -> None:
    now = START + timedelta(minutes=2, seconds=17)

    request = parse_candle_request(
        "BTC/USD",
        "1m",
        "2026-06-19T00:00:30Z",
        None,
        max_range_days=30,
        max_candles=1000,
        clock=lambda: now,
    )

    assert request.end == now


@pytest.mark.parametrize(
    ("timeframe", "start", "end", "code"),
    [
        ("2m", "2026-06-19T00:00:00Z", "2026-06-19T00:02:00Z", "UNSUPPORTED_TIMEFRAME"),
        ("1m", None, "2026-06-19T00:02:00Z", "INVALID_TIME_RANGE"),
        ("1m", "2026-06-19T00:00:00Z", "", "INVALID_TIME_RANGE"),
        ("1m", "2026-06-19T00:02:00Z", "2026-06-19T00:02:00Z", "INVALID_TIME_RANGE"),
        ("1m", "2026-06-19T00:00:00+07:00", "2026-06-19T00:02:00Z", "INVALID_TIME_RANGE"),
    ],
)
def test_parse_candle_request_rejects_invalid_contract(
    timeframe: str,
    start: str | None,
    end: str,
    code: str,
) -> None:
    with pytest.raises(CandleRequestError) as exc_info:
        parse_candle_request(
            "BTC/USD",
            timeframe,
            start,
            end,
            max_range_days=30,
            max_candles=1000,
        )
    assert exc_info.value.code == code


def test_parse_candle_request_enforces_range_and_count_limits() -> None:
    with pytest.raises(CandleRequestError):
        parse_candle_request(
            "BTC/USD",
            "1d",
            "2026-05-01T00:00:00Z",
            "2026-06-19T00:00:00Z",
            max_range_days=30,
            max_candles=1000,
        )


def test_parse_candle_request_counts_partial_slots_with_ceiling() -> None:
    with pytest.raises(CandleRequestError):
        parse_candle_request(
            "BTC/USD",
            "1m",
            "2026-06-19T00:00:30Z",
            "2026-06-19T00:02:00Z",
            max_range_days=30,
            max_candles=1,
        )
    with pytest.raises(CandleRequestError):
        parse_candle_request(
            "BTC/USD",
            "1m",
            "2026-06-19T00:00:00Z",
            "2026-06-19T00:03:00Z",
            max_range_days=30,
            max_candles=2,
        )


def test_find_gaps_uses_half_open_slots_and_contiguous_ranges() -> None:
    persisted = [make_candle(START + timedelta(minutes=1))]
    timeframe = get_timeframe("1m")
    assert timeframe is not None
    schedule = get_candle_schedule(BTC, timeframe)
    expected = schedule.expected_opens(
        START,
        START + timedelta(minutes=3),
        get_market_session_policy(BTC),
        "1m",
    )

    assert _find_gaps(
        persisted,
        expected,
        schedule,
    ) == (
        ProviderFetchSection(
            START,
            START + timedelta(minutes=1),
            1,
        ),
        ProviderFetchSection(
            START + timedelta(minutes=2),
            START + timedelta(minutes=3),
            1,
        ),
    )


async def test_service_rejects_exact_schedule_count_before_provider_call() -> None:
    provider = FakeProvider()
    service = CandleService(
        FakeRepository(symbol=BTC),
        provider,
        max_candles=1,
    )

    with pytest.raises(CandleRequestError) as exc_info:
        await service.get_candles(
            CandleRequest("BTC/USD", "1m", START, START + timedelta(minutes=2))
        )

    assert exc_info.value.code == "INVALID_TIME_RANGE"
    assert provider.calls == []


async def test_service_skips_provider_on_full_database_hit() -> None:
    persisted = [make_candle(START), make_candle(START + timedelta(minutes=1))]
    repository = FakeRepository(persisted)
    provider = FakeProvider()
    service = CandleService(repository, provider)

    result = await service.get_candles(
        CandleRequest("BTC/USD", "1m", START, START + timedelta(minutes=2))
    )

    assert result.candles == persisted
    assert provider.calls == []


async def test_service_skips_twelvedata_when_forex_range_is_fully_persisted() -> None:
    persisted = [
        make_candle(START, symbol=EUR),
        make_candle(START + timedelta(minutes=1), symbol=EUR),
    ]
    provider = FakeProvider()
    service = CandleService(FakeRepository(persisted, symbol=EUR), provider)

    result = await service.get_candles(
        CandleRequest("EUR/USD", "1m", START, START + timedelta(minutes=2))
    )

    assert result.candles == persisted
    assert provider.calls == []


async def test_service_recognizes_persisted_offset_hourly_candle() -> None:
    open_time = datetime(2026, 6, 22, 13, 30, tzinfo=UTC)
    persisted = Candle(
        symbol=SPY.symbol,
        asset_class=SPY.asset_class,
        provider=SPY.provider,
        provider_symbol=SPY.provider_symbol,
        timeframe="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1) - timedelta(milliseconds=1),
        open=Decimal("600"),
        high=Decimal("602"),
        low=Decimal("599"),
        close=Decimal("601"),
        volume=Decimal("1000"),
        complete=True,
    )
    provider = FakeProvider()
    service = CandleService(FakeRepository([persisted], symbol=SPY), provider)

    result = await service.get_candles(
        CandleRequest(
            "SPY",
            "1h",
            datetime(2026, 6, 22, 13, 0, tzinfo=UTC),
            datetime(2026, 6, 22, 14, 0, tzinfo=UTC),
        )
    )

    assert result.candles == [persisted]
    assert provider.calls == []


async def test_service_fetches_missing_forex_range_through_selected_provider() -> None:
    fetched = make_candle(START, symbol=EUR, complete=False)
    repository = FakeRepository(symbol=EUR)
    provider = FakeProvider([fetched])
    service = CandleService(
        repository,
        provider,
        clock=lambda: START + timedelta(minutes=10),
    )

    result = await service.get_candles(
        CandleRequest("EUR/USD", "1m", START, START + timedelta(minutes=2))
    )

    assert provider.calls == [(START, START + timedelta(minutes=2), 3)]
    assert result.candles == [repository.upserted[0]]
    assert result.candles[0].provider == "TWELVE_DATA"
    assert result.candles[0].provider_symbol == "EUR/USD"


async def test_service_splits_forex_provider_ranges_around_weekend_close() -> None:
    friday_open = datetime(2026, 6, 19, 20, 0, tzinfo=UTC)
    sunday_open = datetime(2026, 6, 21, 21, 0, tzinfo=UTC)
    provider = FakeProvider()
    service = CandleService(FakeRepository(symbol=EUR), provider)

    result = await service.get_candles(
        CandleRequest(
            "EUR/USD",
            "1h",
            friday_open,
            sunday_open + timedelta(hours=1),
        )
    )

    assert result.candles == []
    assert provider.calls == [
        (friday_open, friday_open + timedelta(hours=1), 2),
        (sunday_open, sunday_open + timedelta(hours=1), 2),
    ]


async def test_service_skips_provider_for_closed_only_forex_range() -> None:
    start = datetime(2026, 6, 20, 0, 0, tzinfo=UTC)
    provider = FakeProvider()
    service = CandleService(FakeRepository(symbol=EUR), provider)

    result = await service.get_candles(
        CandleRequest("EUR/USD", "1h", start, start + timedelta(hours=24))
    )

    assert result.candles == []
    assert provider.calls == []


async def test_service_requests_only_regular_session_etf_slots() -> None:
    start = datetime(2026, 6, 22, 13, 0, tzinfo=UTC)
    provider = FakeProvider()
    service = CandleService(FakeRepository(symbol=SPY), provider)

    result = await service.get_candles(
        CandleRequest("SPY", "1h", start, start + timedelta(hours=8))
    )

    assert result.candles == []
    assert provider.calls == [
        (
            datetime(2026, 6, 22, 13, 30, tzinfo=UTC),
            datetime(2026, 6, 22, 20, 30, tzinfo=UTC),
            8,
        )
    ]


async def test_service_splits_wti_ranges_around_daily_maintenance() -> None:
    start = datetime(2026, 6, 22, 20, 0, tzinfo=UTC)
    provider = FakeProvider()
    service = CandleService(FakeRepository(symbol=WTI), provider)

    result = await service.get_candles(
        CandleRequest("WTI", "1h", start, start + timedelta(hours=3))
    )

    assert result.candles == []
    assert provider.calls == [
        (
            datetime(2026, 6, 22, 20, 30, tzinfo=UTC),
            datetime(2026, 6, 22, 21, 30, tzinfo=UTC),
            2,
        ),
        (
            datetime(2026, 6, 22, 22, 30, tzinfo=UTC),
            datetime(2026, 6, 22, 23, 30, tzinfo=UTC),
            2,
        ),
    ]


async def test_service_excludes_persisted_and_cached_closed_session_forex_candles() -> None:
    cache = CandleCache()
    weekend_open = datetime(2026, 6, 20, 0, 0, tzinfo=UTC)
    weekend = make_candle(weekend_open, symbol=EUR)
    await cache.put(weekend)
    provider = FakeProvider()
    service = CandleService(
        FakeRepository([weekend], symbol=EUR),
        provider,
        cache=cache,
    )

    result = await service.get_candles(
        CandleRequest(
            "EUR/USD",
            "1m",
            weekend_open,
            weekend_open + timedelta(minutes=1),
        )
    )

    assert result.candles == []
    assert provider.calls == []


async def test_service_preserves_non_forex_weekend_gap_behavior() -> None:
    weekend_open = datetime(2026, 6, 20, 0, 0, tzinfo=UTC)
    provider = FakeProvider()
    service = CandleService(FakeRepository(symbol=BTC), provider)

    await service.get_candles(
        CandleRequest(
            "BTC/USD",
            "1m",
            weekend_open,
            weekend_open + timedelta(minutes=2),
        )
    )

    assert provider.calls == [(weekend_open, weekend_open + timedelta(minutes=2), 3)]


async def test_service_fetches_only_gaps_and_does_not_synthesize_missing_slots() -> None:
    persisted = [make_candle(START + timedelta(minutes=1), close="20")]
    fetched = [make_candle(START, complete=False)]
    repository = FakeRepository(persisted)
    provider = FakeProvider(fetched)
    service = CandleService(
        repository,
        provider,
        clock=lambda: START + timedelta(minutes=10),
    )

    result = await service.get_candles(
        CandleRequest("BTC/USD", "1m", START, START + timedelta(minutes=3))
    )

    assert provider.calls == [
        (START, START + timedelta(minutes=1), 2),
        (START + timedelta(minutes=2), START + timedelta(minutes=3), 2),
    ]
    assert [candle.open_time for candle in result.candles] == [
        START,
        START + timedelta(minutes=1),
    ]
    assert repository.upserted == [result.candles[0]]


async def test_service_returns_forming_candle_without_persisting_it() -> None:
    forming = make_candle(START, complete=False)
    repository = FakeRepository()
    service = CandleService(
        repository,
        FakeProvider([forming]),
        clock=lambda: forming.close_time,
    )

    result = await service.get_candles(
        CandleRequest("BTC/USD", "1m", START, START + timedelta(minutes=1))
    )

    assert result.candles[0].complete is False
    assert repository.upserted == []


async def test_service_merges_cached_forming_candle_in_range_without_persisting() -> None:
    cache = CandleCache()
    current = make_candle(START + timedelta(minutes=1), complete=False, close="20")
    await cache.put(current)
    repository = FakeRepository([make_candle(START)])
    provider = FakeProvider()
    service = CandleService(repository, provider, cache=cache)

    result = await service.get_candles(
        CandleRequest("BTC/USD", "1m", START, START + timedelta(minutes=2))
    )

    assert [candle.open_time for candle in result.candles] == [
        START,
        START + timedelta(minutes=1),
    ]
    assert result.candles[1] == current
    assert repository.upserted == []


async def test_service_ignores_cached_forming_candle_outside_range() -> None:
    cache = CandleCache()
    await cache.put(make_candle(START + timedelta(minutes=5), complete=False))
    service = CandleService(FakeRepository([make_candle(START)]), FakeProvider(), cache=cache)

    result = await service.get_candles(
        CandleRequest("BTC/USD", "1m", START, START + timedelta(minutes=1))
    )

    assert [candle.open_time for candle in result.candles] == [START]


async def test_service_retains_persisted_candle_on_provider_overlap() -> None:
    persisted = make_candle(START, close="10.25")

    class OverlappingProvider(FakeProvider):
        async def fetch_candles(
            self,
            symbol: SupportedSymbol,
            timeframe: str,
            provider_interval: str,
            start: datetime,
            end: datetime,
            limit: int,
        ) -> list[Candle]:
            del symbol, timeframe, provider_interval, start, end, limit
            return [
                make_candle(START, close="99.00"),
                make_candle(START + timedelta(minutes=1), close="20.00"),
            ]

    service = CandleService(
        FakeRepository([persisted]),
        OverlappingProvider(),
        clock=lambda: START + timedelta(minutes=10),
    )

    result = await service.get_candles(
        CandleRequest("BTC/USD", "1m", START, START + timedelta(minutes=2))
    )

    assert [candle.close for candle in result.candles] == [
        Decimal("10.25"),
        Decimal("20.00"),
    ]


async def test_service_rejects_unsupported_symbol_before_provider_call() -> None:
    provider = FakeProvider()
    service = CandleService(FakeRepository(symbol=None), provider)

    with pytest.raises(CandleRequestError) as exc_info:
        await service.get_candles(
            CandleRequest("SOL/USD", "1m", START, START + timedelta(minutes=1))
        )

    assert exc_info.value.code == "UNSUPPORTED_SYMBOL"
    assert provider.calls == []


@pytest.mark.parametrize(
    "error",
    [DatabaseUnavailableError(), ProviderUnavailableError()],
)
async def test_service_propagates_sanitized_boundary_errors(error: Exception) -> None:
    if isinstance(error, DatabaseUnavailableError):

        class FailingRepository(FakeRepository):
            async def get_enabled_symbol(self, symbol: str) -> SupportedSymbol | None:
                del symbol
                raise error

        service = CandleService(FailingRepository(), FakeProvider())
    else:

        class FailingProvider(FakeProvider):
            async def fetch_candles(
                self,
                symbol: SupportedSymbol,
                timeframe: str,
                provider_interval: str,
                start: datetime,
                end: datetime,
                limit: int,
            ) -> list[Candle]:
                del symbol, timeframe, provider_interval, start, end, limit
                raise error

        service = CandleService(FakeRepository(), FailingProvider())

    with pytest.raises(type(error)):
        await service.get_candles(
            CandleRequest("BTC/USD", "1m", START, START + timedelta(minutes=1))
        )
