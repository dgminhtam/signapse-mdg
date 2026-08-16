import asyncio
import logging
import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

import pandas as pd
import pytest

from app.core import observability
from app.domain.errors import ProviderUnavailableError
from app.domain.symbols import SupportedSymbol
from app.providers.yfinance_market_data import (
    SUPPORTED_YFINANCE_PROVIDER_SYMBOLS,
    YFinanceQuoteProvider,
    _install_timeout,
)


class FakeTicker:
    def __init__(
        self,
        payload: dict[str, object] | None = None,
        error: Exception | None = None,
        callback: object | None = None,
    ) -> None:
        self.payload = payload or {}
        self.error = error
        self.callback = callback

    def get_info(self) -> dict[str, object]:
        if callable(self.callback):
            self.callback()
        if self.error is not None:
            raise self.error
        return self.payload


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def request(self, method: str, url: str, **kwargs: object) -> object:
        self.calls.append((method, url, kwargs))
        return object()


def make_provider(
    payloads: dict[str, dict[str, object] | Exception],
    *,
    session_factory: object | None = None,
    callback: object | None = None,
) -> tuple[YFinanceQuoteProvider, list[str]]:
    calls: list[str] = []

    def ticker_factory(symbol: str, session: object) -> FakeTicker:
        assert session is not None
        calls.append(symbol)
        value = payloads[symbol]
        if isinstance(value, Exception):
            return FakeTicker(error=value, callback=callback)
        return FakeTicker(value, callback=callback)

    provider = YFinanceQuoteProvider(
        2.5,
        session_factory=cast(
            object,
            session_factory or (lambda timeout: FakeSession()),
        ),
        ticker_factory=ticker_factory,
    )
    return provider, calls


YFINANCE_SILVER = SupportedSymbol("XAG/USD", "COMMODITY", "YFINANCE", "SI=F", True, 3)
YFINANCE_EURUSD = SupportedSymbol("EUR/USD", "FOREX", "YFINANCE", "EURUSD=X", True, 5)
START = datetime(2026, 6, 22, 0, 0, tzinfo=UTC)
EURUSD_REGRESSION_START = datetime(2026, 1, 21, 0, 0, tzinfo=UTC)


def make_history_provider(
    payload: object,
    *,
    session_factory: object | None = None,
    callback: object | None = None,
) -> tuple[YFinanceQuoteProvider, list[dict[str, object]]]:
    calls: list[dict[str, object]] = []

    def download_factory(**kwargs: object) -> object:
        calls.append(kwargs)
        if callable(callback):
            callback()
        return payload

    provider = YFinanceQuoteProvider(
        2.5,
        session_factory=cast(
            object,
            session_factory or (lambda timeout: FakeSession()),
        ),
        ticker_factory=lambda symbol, session: FakeTicker(
            {"regularMarketPrice": "1"},
        ),
        download_factory=download_factory,
    )
    return provider, calls


def make_history_frame(
    rows: list[dict[str, object]],
    index: list[object] | None = None,
) -> pd.DataFrame:
    values = pd.DataFrame(rows)
    values.index = pd.Index(index or [START + timedelta(minutes=i) for i in range(len(rows))])
    return values


async def test_provider_uses_get_info_regular_market_price_for_allowlist() -> None:
    assert SUPPORTED_YFINANCE_PROVIDER_SYMBOLS == {
        "AAPL",
        "AUDUSD=X",
        "BZ=F",
        "BTC-USD",
        "KC=F",
        "ZC=F",
        "^DJI",
        "ETH-USD",
        "EURUSD=X",
        "GBPUSD=X",
        "MSFT",
        "NG=F",
        "^NDX",
        "NVDA",
        "QQQ",
        "^GSPC",
        "SPY",
        "SB=F",
        "TSLA",
        "JPY=X",
        "ZW=F",
        "CL=F",
        "SI=F",
    }
    payloads = {
        symbol: {"regularMarketPrice": str(index + 1)}
        for index, symbol in enumerate(sorted(SUPPORTED_YFINANCE_PROVIDER_SYMBOLS))
    }
    provider, calls = make_provider(payloads)

    result = await provider.fetch_latest_prices(
        sorted(SUPPORTED_YFINANCE_PROVIDER_SYMBOLS) + ["GC=F"]
    )

    assert calls == sorted(SUPPORTED_YFINANCE_PROVIDER_SYMBOLS)
    assert result.prices == {
        symbol: Decimal(str(index + 1))
        for index, symbol in enumerate(sorted(SUPPORTED_YFINANCE_PROVIDER_SYMBOLS))
    }
    assert result.unavailable_symbols == frozenset({"GC=F"})


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (12, Decimal("12")),
        (12.5, Decimal("12.5")),
        ("12.5000", Decimal("12.5000")),
        (Decimal("12.50"), Decimal("12.50")),
    ],
)
async def test_provider_normalizes_valid_regular_market_prices(
    value: object,
    expected: Decimal,
) -> None:
    provider, _ = make_provider({"SI=F": {"regularMarketPrice": value}})

    result = await provider.fetch_latest_prices(["SI=F"])

    assert result.prices == {"SI=F": expected}
    assert result.unavailable_symbols == frozenset()


@pytest.mark.parametrize(
    "value",
    [None, True, False, object(), "", "bad", "NaN", "Infinity", 0, -1],
)
async def test_provider_marks_invalid_regular_market_prices_unavailable(value: object) -> None:
    provider, _ = make_provider({"SI=F": {"regularMarketPrice": value}})

    result = await provider.fetch_latest_prices(["SI=F"])

    assert result.prices == {}
    assert result.unavailable_symbols == frozenset({"SI=F"})


async def test_provider_isolates_ticker_failure_and_deduplicates_symbols() -> None:
    provider, calls = make_provider(
        {
            "SI=F": RuntimeError("secret"),
            "^GSPC": {"regularMarketPrice": "7472.79"},
        }
    )

    result = await provider.fetch_latest_prices(["SI=F", "^GSPC", "SI=F"])

    assert calls == ["SI=F", "^GSPC"]
    assert result.prices == {"^GSPC": Decimal("7472.79")}
    assert result.unavailable_symbols == frozenset({"SI=F"})


async def test_provider_maps_session_setup_failure_to_provider_unavailable() -> None:
    def fail_session(timeout: float) -> object:
        raise RuntimeError(f"secret {timeout}")

    provider, _ = make_provider({}, session_factory=fail_session)

    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_latest_prices(["SI=F"])


def test_session_timeout_is_clamped_to_configured_value() -> None:
    session = FakeSession()
    _install_timeout(session, 2.5)

    session.request("GET", "https://example.test", timeout=30)

    assert session.calls == [
        ("GET", "https://example.test", {"timeout": 2.5}),
    ]


async def test_slow_provider_call_does_not_block_event_loop() -> None:
    started = threading.Event()
    release = threading.Event()

    def block() -> None:
        started.set()
        release.wait(timeout=1)

    provider, _ = make_provider(
        {"SI=F": {"regularMarketPrice": "63.2"}},
        callback=block,
    )
    task = asyncio.create_task(provider.fetch_latest_prices(["SI=F"]))
    while not started.is_set():
        await asyncio.sleep(0)

    loop_progressed = False
    await asyncio.sleep(0)
    loop_progressed = True
    release.set()
    result = await task

    assert loop_progressed
    assert result.prices == {"SI=F": Decimal("63.2")}


async def test_concurrent_calls_are_serialized() -> None:
    first_started = threading.Event()
    release_first = threading.Event()
    call_count = 0

    def block_first() -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            first_started.set()
            release_first.wait(timeout=1)

    provider, calls = make_provider(
        {
            "SI=F": {"regularMarketPrice": "63.2"},
            "^GSPC": {"regularMarketPrice": "7472.79"},
        },
        callback=block_first,
    )
    first = asyncio.create_task(provider.fetch_latest_prices(["SI=F"]))
    while not first_started.is_set():
        await asyncio.sleep(0)
    second = asyncio.create_task(provider.fetch_latest_prices(["^GSPC"]))
    await asyncio.sleep(0.02)

    assert calls == ["SI=F"]
    release_first.set()
    await asyncio.gather(first, second)
    assert calls == ["SI=F", "^GSPC"]


async def test_cancelled_call_propagates() -> None:
    started = threading.Event()
    release = threading.Event()

    def block() -> None:
        started.set()
        release.wait(timeout=1)

    provider, _ = make_provider(
        {"SI=F": {"regularMarketPrice": "63.2"}},
        callback=block,
    )
    task = asyncio.create_task(provider.fetch_latest_prices(["SI=F"]))
    while not started.is_set():
        await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()


async def test_candles_call_yfinance_download_with_expected_arguments() -> None:
    frame = make_history_frame(
        [
            {
                "Open": "10.00",
                "High": "11.00",
                "Low": "9.50",
                "Close": "10.50",
                "Volume": "123",
            }
        ]
    )
    session = FakeSession()
    provider, calls = make_history_provider(frame, session_factory=lambda timeout: session)

    candles = await provider.fetch_candles(
        YFINANCE_SILVER,
        "1m",
        "1m",
        START,
        START + timedelta(minutes=1),
        2,
    )

    assert len(candles) == 1
    assert calls == [
        {
            "tickers": "SI=F",
            "start": START,
            "end": START + timedelta(minutes=1),
            "interval": "1m",
            "timeout": 2.5,
            "session": session,
            "threads": False,
            "progress": False,
            "actions": False,
            "auto_adjust": False,
            "multi_level_index": False,
        }
    ]


@pytest.mark.parametrize(
    ("provider_interval", "expected"),
    [
        ("1m", "1m"),
        ("5m", "5m"),
        ("15m", "15m"),
        ("30m", "30m"),
        ("1h", "1h"),
        ("4h", "4h"),
        ("1d", "1d"),
        ("1w", "1wk"),
        ("1mo", "1mo"),
    ],
)
async def test_candles_map_supported_timeframes(
    provider_interval: str,
    expected: str,
) -> None:
    provider, calls = make_history_provider(pd.DataFrame())

    result = await provider.fetch_candles(
        YFINANCE_SILVER,
        provider_interval,
        provider_interval,
        START,
        START + timedelta(days=1),
        1,
    )

    assert result == []
    assert calls[0]["interval"] == expected


async def test_candles_derives_monthly_close_time_by_calendar_month() -> None:
    open_time = datetime(2026, 2, 1, tzinfo=UTC)
    frame = make_history_frame(
        [
            {
                "Open": "10.00",
                "High": "11.00",
                "Low": "9.50",
                "Close": "10.50",
                "Volume": "123",
            }
        ],
        index=[open_time],
    )
    provider, _ = make_history_provider(frame)

    candles = await provider.fetch_candles(
        YFINANCE_SILVER,
        "1mo",
        "1mo",
        open_time,
        datetime(2026, 3, 1, tzinfo=UTC),
        1,
    )

    assert candles[0].close_time == datetime(2026, 3, 1, tzinfo=UTC) - timedelta(milliseconds=1)


async def test_candles_reject_unsupported_symbol_without_provider_call() -> None:
    provider, calls = make_history_provider(pd.DataFrame())

    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_candles(
            SupportedSymbol("XAU/USD", "COMMODITY", "YFINANCE", "GC=F", True, 2),
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )

    assert calls == []


async def test_candles_accept_every_approved_provider_symbol() -> None:
    provider, calls = make_history_provider(pd.DataFrame())

    for provider_symbol in sorted(SUPPORTED_YFINANCE_PROVIDER_SYMBOLS):
        candles = await provider.fetch_candles(
            SupportedSymbol(provider_symbol, "TEST", "YFINANCE", provider_symbol, True, 2),
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )
        assert candles == []

    assert [call["tickers"] for call in calls] == sorted(SUPPORTED_YFINANCE_PROVIDER_SYMBOLS)


async def test_candles_normalize_history_rows_and_filter_half_open_range() -> None:
    frame = make_history_frame(
        [
            {
                "Open": "10.00",
                "High": "11.00",
                "Low": "9.50",
                "Close": "10.50",
                "Volume": "123.0000",
            },
            {
                "Open": "12.00",
                "High": "13.00",
                "Low": "11.50",
                "Close": "12.50",
                "Volume": "456",
            },
        ],
        index=[
            START,
            START + timedelta(minutes=1),
        ],
    )
    provider, _ = make_history_provider(frame)

    candles = await provider.fetch_candles(
        YFINANCE_SILVER,
        "1m",
        "1m",
        START,
        START + timedelta(minutes=1),
        2,
    )

    assert len(candles) == 1
    candle = candles[0]
    assert candle.symbol == "XAG/USD"
    assert candle.provider == "YFINANCE"
    assert candle.provider_symbol == "SI=F"
    assert candle.open_time == START
    assert candle.close_time == START + timedelta(minutes=1) - timedelta(milliseconds=1)
    assert candle.open == Decimal("10.00")
    assert candle.high == Decimal("11.00")
    assert candle.low == Decimal("9.50")
    assert candle.close == Decimal("10.50")
    assert candle.volume == Decimal("123.0000")
    assert candle.complete is False


async def test_candles_quarantine_eurusd_ohlc_row_and_log_safe_partial_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="app.providers.yfinance_market_data")
    frame = make_history_frame(
        [
            {
                "Open": "1.172608",
                "High": "1.174260",
                "Low": "1.169700",
                "Close": "1.172787",
                "Volume": "0",
            },
            {
                "Open": "1.167392",
                "High": "1.175074",
                "Low": "1.167392",
                "Close": "1.167297",
                "Volume": "0",
            },
            {
                "Open": "1.175392",
                "High": "1.177565",
                "Low": "1.172897",
                "Close": "1.175461",
                "Volume": "0",
            },
        ],
        index=[
            EURUSD_REGRESSION_START,
            EURUSD_REGRESSION_START + timedelta(days=1),
            EURUSD_REGRESSION_START + timedelta(days=2),
        ],
    )
    provider, _ = make_history_provider(frame)

    candles = await provider.fetch_candles(
        YFINANCE_EURUSD,
        "1d",
        "1d",
        EURUSD_REGRESSION_START,
        EURUSD_REGRESSION_START + timedelta(days=3),
        3,
    )

    assert [candle.open_time for candle in candles] == [
        EURUSD_REGRESSION_START,
        EURUSD_REGRESSION_START + timedelta(days=2),
    ]
    assert candles[0].close == Decimal("1.172787")
    assert candles[1].close == Decimal("1.175461")

    records = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "yfinance_candle_rows_quarantined"
    ]
    assert len(records) == 1
    fields = records[0].diagnostic_fields
    assert fields["failure_reason"] == "INVALID_PAYLOAD"
    assert fields["retryable"] is False
    assert fields["action"] == "ROW_QUARANTINED"
    assert fields["partial"] is True
    assert fields["skipped_count"] == 1
    assert fields["skipped_rows"] == [
        {
            "failed_row_timestamp": "2026-01-22T00:00:00+00:00",
            "failed_row_reason": "history row violates OHLC bounds",
            "open": "1.167392",
            "high": "1.175074",
            "low": "1.167392",
            "close": "1.167297",
        }
    ]
    assert "DataFrame" not in caplog.text


async def test_candles_quarantine_warning_is_rate_limited_with_suppressed_count(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ControlledLimiter:
        def __init__(self) -> None:
            self.responses = [(True, 0), (False, 0), (True, 2)]
            self.keys: list[str] = []

        def allow(self, key: str) -> tuple[bool, int]:
            self.keys.append(key)
            return self.responses.pop(0)

    limiter = ControlledLimiter()
    monkeypatch.setattr(observability, "_warning_limiter", limiter)
    caplog.set_level(logging.WARNING, logger="app.providers.yfinance_market_data")
    frame = make_history_frame(
        [
            {
                "Open": "1.0",
                "High": "1.1",
                "Low": "1.0",
                "Close": "1.0",
                "Volume": "0",
            },
            {
                "Open": "1.0",
                "High": "1.1",
                "Low": "1.0",
                "Close": "0.9",
                "Volume": "0",
            },
        ],
        index=[EURUSD_REGRESSION_START, EURUSD_REGRESSION_START + timedelta(days=1)],
    )
    provider, calls = make_history_provider(frame)

    for _ in range(3):
        await provider.fetch_candles(
            YFINANCE_EURUSD,
            "1d",
            "1d",
            EURUSD_REGRESSION_START,
            EURUSD_REGRESSION_START + timedelta(days=2),
            2,
        )

    records = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "yfinance_candle_rows_quarantined"
    ]
    assert len(calls) == 3
    assert len(records) == 2
    assert (
        limiter.keys
        == ["YFINANCE:EURUSD=X:1d:2026-01-22 00:00:00+00:00:history row violates OHLC bounds"] * 3
    )
    assert records[1].diagnostic_fields["suppressed_count"] == 2


async def test_candles_rejects_all_ohlc_bounds_invalid_rows_without_partial_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="app.providers.yfinance_market_data")
    frame = make_history_frame(
        [
            {"Open": "10", "High": "11", "Low": "12", "Close": "10", "Volume": "0"},
            {"Open": "10", "High": "9", "Low": "9", "Close": "10", "Volume": "0"},
        ],
        index=[START, START + timedelta(minutes=1)],
    )
    provider, _ = make_history_provider(frame)

    with pytest.raises(ProviderUnavailableError) as exc_info:
        await provider.fetch_candles(
            YFINANCE_SILVER,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=2),
            2,
        )

    assert exc_info.value.failure_reason == "INVALID_PAYLOAD"
    assert not [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "yfinance_candle_rows_quarantined"
    ]


async def test_candles_reject_mixed_structural_error_without_retry_or_partial_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="app.providers.yfinance_market_data")
    frame = make_history_frame(
        [
            {"Open": "10", "High": "11", "Low": "9", "Close": "10", "Volume": "0"},
            {"Open": "bad", "High": "11", "Low": "9", "Close": "10", "Volume": "0"},
        ],
        index=[START, START + timedelta(minutes=1)],
    )
    provider, calls = make_history_provider(frame)

    with pytest.raises(ProviderUnavailableError) as exc_info:
        await provider.fetch_candles(
            YFINANCE_SILVER,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=2),
            2,
        )

    assert exc_info.value.failure_reason == "INVALID_PAYLOAD"
    assert len(calls) == 1
    assert not [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "yfinance_candle_rows_quarantined"
    ]


async def test_candles_convert_timezone_aware_index_to_utc() -> None:
    frame = make_history_frame(
        [
            {
                "Open": "10.00",
                "High": "11.00",
                "Low": "9.50",
                "Close": "10.50",
                "Volume": "0",
            }
        ],
        index=[pd.Timestamp("2026-06-21T20:00:00-04:00")],
    )
    provider, _ = make_history_provider(frame)

    candles = await provider.fetch_candles(
        YFINANCE_SILVER,
        "1m",
        "1m",
        START,
        START + timedelta(minutes=1),
        1,
    )

    assert candles[0].open_time == START


async def test_candles_use_zero_for_missing_volume() -> None:
    frame = make_history_frame(
        [
            {
                "Open": "10.00",
                "High": "11.00",
                "Low": "9.50",
                "Close": "10.50",
                "Volume": pd.NA,
            }
        ]
    )
    provider, _ = make_history_provider(frame)

    candles = await provider.fetch_candles(
        YFINANCE_SILVER,
        "1m",
        "1m",
        START,
        START + timedelta(minutes=1),
        1,
    )

    assert candles[0].volume == Decimal("0")


@pytest.mark.parametrize(
    "row",
    [
        {"Open": "bad", "High": "11", "Low": "9", "Close": "10", "Volume": "0"},
        {"Open": "10", "High": "9", "Low": "9", "Close": "10", "Volume": "0"},
        {"Open": "10", "High": "11", "Low": "12", "Close": "10", "Volume": "0"},
        {"Open": "10", "High": "11", "Low": "9", "Close": "10", "Volume": "-1"},
    ],
)
async def test_candles_reject_invalid_history_rows(row: dict[str, object]) -> None:
    frame = make_history_frame([row])
    provider, _ = make_history_provider(frame)

    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_candles(
            YFINANCE_SILVER,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )


async def test_candles_reject_duplicate_open_times() -> None:
    frame = make_history_frame(
        [
            {"Open": "10", "High": "11", "Low": "9", "Close": "10", "Volume": "0"},
            {"Open": "10", "High": "11", "Low": "9", "Close": "10", "Volume": "0"},
        ],
        index=[START, START],
    )
    provider, _ = make_history_provider(frame)

    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_candles(
            YFINANCE_SILVER,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )


async def test_candles_map_download_failure_to_provider_unavailable() -> None:
    def fail(**kwargs: object) -> object:
        del kwargs
        raise RuntimeError("secret")

    provider = YFinanceQuoteProvider(
        2.5,
        session_factory=lambda timeout: FakeSession(),
        ticker_factory=lambda symbol, session: FakeTicker({"regularMarketPrice": "1"}),
        download_factory=fail,
    )

    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_candles(
            YFINANCE_SILVER,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )


async def test_slow_candle_call_does_not_block_event_loop() -> None:
    started = threading.Event()
    release = threading.Event()

    def block() -> None:
        started.set()
        release.wait(timeout=1)

    provider, _ = make_history_provider(pd.DataFrame(), callback=block)
    task = asyncio.create_task(
        provider.fetch_candles(
            YFINANCE_SILVER,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )
    )
    while not started.is_set():
        await asyncio.sleep(0)

    loop_progressed = False
    await asyncio.sleep(0)
    loop_progressed = True
    release.set()
    await task

    assert loop_progressed


async def test_concurrent_candle_calls_are_serialized() -> None:
    first_started = threading.Event()
    release_first = threading.Event()
    call_count = 0

    def block_first() -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            first_started.set()
            release_first.wait(timeout=1)

    provider, calls = make_history_provider(pd.DataFrame(), callback=block_first)
    first = asyncio.create_task(
        provider.fetch_candles(
            YFINANCE_SILVER,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )
    )
    while not first_started.is_set():
        await asyncio.sleep(0)
    second = asyncio.create_task(
        provider.fetch_candles(
            YFINANCE_SILVER,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )
    )
    await asyncio.sleep(0.02)

    assert len(calls) == 1
    release_first.set()
    await asyncio.gather(first, second)
    assert len(calls) == 2


async def test_cancelled_candle_call_propagates() -> None:
    started = threading.Event()
    release = threading.Event()

    def block() -> None:
        started.set()
        release.wait(timeout=1)

    provider, _ = make_history_provider(pd.DataFrame(), callback=block)
    task = asyncio.create_task(
        provider.fetch_candles(
            YFINANCE_SILVER,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )
    )
    while not started.is_set():
        await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()
