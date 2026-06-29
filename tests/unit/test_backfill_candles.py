from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import StringIO

import pytest

from app.backfill_candles import (
    BackfillOptions,
    iter_chunks,
    parse_arguments,
    process_backfill,
    select_symbols,
)
from app.domain.candles import Candle, CandleRequest, CandleResult
from app.domain.symbols import SupportedSymbol
from app.services.candles import CandleService

BTC = SupportedSymbol("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True)
EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True)
START = datetime(2026, 6, 19, 0, 0, tzinfo=UTC)


class FakeBackfillService:
    def __init__(self, *, fail_on: datetime | None = None) -> None:
        self.fail_on = fail_on
        self.requests: list[CandleRequest] = []

    async def get_candles(self, request: CandleRequest) -> CandleResult:
        self.requests.append(request)
        if self.fail_on is not None and request.start == self.fail_on:
            raise RuntimeError("provider down")
        return CandleResult(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start=request.start,
            end=request.end,
            candles=[],
        )


class FakeCandleRepository:
    def __init__(self, persisted: list[Candle]) -> None:
        self.persisted = persisted
        self.upserted: list[Candle] = []

    async def get_enabled_symbol(self, symbol: str) -> SupportedSymbol | None:
        return BTC if symbol == BTC.symbol else None

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


class FakeCandleProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[datetime, datetime]] = []

    async def fetch_candles(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[Candle]:
        del symbol, timeframe, provider_interval, limit
        self.calls.append((start, end))
        return []


def make_complete_candle(open_time: datetime) -> Candle:
    return Candle(
        symbol=BTC.symbol,
        asset_class=BTC.asset_class,
        provider=BTC.provider,
        provider_symbol=BTC.provider_symbol,
        timeframe="1m",
        open_time=open_time,
        close_time=open_time + timedelta(minutes=1) - timedelta(milliseconds=1),
        open=Decimal("10"),
        high=Decimal("11"),
        low=Decimal("9"),
        close=Decimal("10.5"),
        volume=Decimal("1"),
        complete=True,
    )


def test_parse_arguments_accepts_filters_and_utc_range() -> None:
    options = parse_arguments(
        [
            "--from",
            "2026-06-19T00:00:00Z",
            "--to",
            "2026-06-19T00:10:00+00:00",
            "--timeframes",
            "1m,5m",
            "--symbols",
            "BTC/USD,EUR/USD",
            "--providers",
            "binance_spot",
            "--asset-classes",
            "crypto",
        ]
    )

    assert options.start == START
    assert options.end == START + timedelta(minutes=10)
    assert options.timeframes == ("1m", "5m")
    assert options.symbols == frozenset({"BTC/USD", "EUR/USD"})
    assert options.providers == frozenset({"BINANCE_SPOT"})
    assert options.asset_classes == frozenset({"CRYPTO"})


@pytest.mark.parametrize(
    "argv",
    [
        [
            "--from",
            "2026-06-19T00:00:00+07:00",
            "--to",
            "2026-06-19T00:01:00Z",
            "--timeframes",
            "1m",
        ],
        [
            "--from",
            "2026-06-19T00:00:00Z",
            "--to",
            "2026-06-19T00:01:00Z",
            "--timeframes",
            "2m",
        ],
        [
            "--from",
            "2026-06-19T00:01:00Z",
            "--to",
            "2026-06-19T00:01:00Z",
            "--timeframes",
            "1m",
        ],
    ],
)
def test_parse_arguments_rejects_invalid_scope(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        parse_arguments(argv)


def test_select_symbols_filters_enabled_rows_and_rejects_unknown_explicit_symbol() -> None:
    options = BackfillOptions(
        start=START,
        end=START + timedelta(minutes=1),
        timeframes=("1m",),
        symbols=frozenset({"BTC/USD", "SOL/USD"}),
    )

    with pytest.raises(ValueError):
        select_symbols([BTC, EUR], options)

    selected = select_symbols(
        [BTC, EUR],
        BackfillOptions(
            start=START,
            end=START + timedelta(minutes=1),
            timeframes=("1m",),
            providers=frozenset({"TWELVE_DATA"}),
        ),
    )

    assert selected == (EUR,)


def test_iter_chunks_uses_configured_max_candles() -> None:
    chunks = iter_chunks(BTC, "1m", START, START + timedelta(minutes=5), max_candles=2)

    assert [(chunk.start, chunk.end) for chunk in chunks] == [
        (START, START + timedelta(minutes=2)),
        (START + timedelta(minutes=2), START + timedelta(minutes=4)),
        (START + timedelta(minutes=4), START + timedelta(minutes=5)),
    ]


def test_iter_chunks_handles_monthly_timeframe_by_calendar_months() -> None:
    start = datetime(2026, 1, 15, tzinfo=UTC)
    end = datetime(2026, 5, 1, tzinfo=UTC)

    chunks = iter_chunks(BTC, "1mo", start, end, max_candles=2)

    assert [(chunk.start, chunk.end) for chunk in chunks] == [
        (start, datetime(2026, 3, 15, tzinfo=UTC)),
        (datetime(2026, 3, 15, tzinfo=UTC), end),
    ]


def test_iter_chunks_handles_monthly_range_starting_on_day_31() -> None:
    start = datetime(2026, 1, 31, tzinfo=UTC)

    chunks = iter_chunks(BTC, "1mo", start, datetime(2026, 3, 1, tzinfo=UTC), max_candles=1)

    assert [(chunk.start, chunk.end) for chunk in chunks] == [
        (start, datetime(2026, 2, 28, tzinfo=UTC)),
        (datetime(2026, 2, 28, tzinfo=UTC), datetime(2026, 3, 1, tzinfo=UTC)),
    ]


async def test_process_backfill_calls_service_for_each_chunk() -> None:
    service = FakeBackfillService()
    stdout = StringIO()

    exit_code = await process_backfill(
        options=BackfillOptions(
            start=START,
            end=START + timedelta(minutes=3),
            timeframes=("1m",),
        ),
        symbols=[BTC],
        service=service,
        max_candles=2,
        stdout=stdout,
    )

    assert exit_code == 0
    assert [(request.start, request.end) for request in service.requests] == [
        (START, START + timedelta(minutes=2)),
        (START + timedelta(minutes=2), START + timedelta(minutes=3)),
    ]
    assert "ok symbol=BTC/USD timeframe=1m" in stdout.getvalue()


async def test_process_backfill_reports_failures_and_continues() -> None:
    service = FakeBackfillService(fail_on=START + timedelta(minutes=2))
    stderr = StringIO()

    exit_code = await process_backfill(
        options=BackfillOptions(
            start=START,
            end=START + timedelta(minutes=3),
            timeframes=("1m",),
        ),
        symbols=[BTC],
        service=service,
        max_candles=2,
        stderr=stderr,
    )

    assert exit_code == 1
    assert len(service.requests) == 2
    assert "failed symbol=BTC/USD timeframe=1m" in stderr.getvalue()
    assert "provider down" not in stderr.getvalue()


async def test_backfill_reuses_candle_service_persisted_gap_behavior() -> None:
    repository = FakeCandleRepository(
        [make_complete_candle(START), make_complete_candle(START + timedelta(minutes=1))]
    )
    provider = FakeCandleProvider()
    service = CandleService(repository, provider)

    exit_code = await process_backfill(
        options=BackfillOptions(
            start=START,
            end=START + timedelta(minutes=2),
            timeframes=("1m",),
        ),
        symbols=[BTC],
        service=service,
        max_candles=1000,
    )

    assert exit_code == 0
    assert provider.calls == []
    assert repository.upserted == []
