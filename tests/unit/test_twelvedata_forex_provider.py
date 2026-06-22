import asyncio
import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from twelvedata.exceptions import TwelveDataError

from app.domain.errors import ProviderUnavailableError
from app.domain.symbols import SupportedSymbol
from app.providers import twelvedata_forex as twelvedata_module
from app.providers.twelvedata_forex import (
    SUPPORTED_FOREX_PROVIDER_SYMBOLS,
    TwelveDataForexProvider,
    build_twelvedata_forex_provider,
)

EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True)
START = datetime(2026, 6, 22, 0, 0, tzinfo=UTC)


class FakeEndpoint:
    def __init__(self, payload: object = None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error

    def as_json(self) -> object:
        if self.error is not None:
            raise self.error
        return self.payload


class FakeClient:
    def __init__(
        self,
        prices: dict[str, object] | None = None,
        time_series_payload: object = None,
        forex_pairs_payload: object = None,
        error: Exception | None = None,
    ) -> None:
        self.prices = prices or {}
        self.time_series_payload = time_series_payload
        self.forex_pairs_payload = forex_pairs_payload
        self.error = error
        self.price_calls: list[str] = []
        self.time_series_calls: list[dict[str, object]] = []
        self.forex_pairs_calls = 0

    def price(self, **defaults: object) -> FakeEndpoint:
        symbol = cast(str, defaults["symbol"])
        self.price_calls.append(symbol)
        if self.error is not None:
            raise self.error
        return FakeEndpoint(self.prices.get(symbol))

    def time_series(self, **defaults: object) -> FakeEndpoint:
        self.time_series_calls.append(defaults)
        if self.error is not None:
            raise self.error
        return FakeEndpoint(self.time_series_payload)

    def get_forex_pairs_list(self, **defaults: object) -> FakeEndpoint:
        del defaults
        self.forex_pairs_calls += 1
        if self.error is not None:
            raise self.error
        return FakeEndpoint(self.forex_pairs_payload)


def candle_row(open_time: datetime = START) -> dict[str, object]:
    return {
        "datetime": open_time.strftime("%Y-%m-%d %H:%M:%S"),
        "open": "1.1000",
        "high": "1.2000",
        "low": "1.0000",
        "close": "1.1500",
        "volume": "0",
    }


async def test_provider_discovers_supported_forex_symbols() -> None:
    client = FakeClient(
        forex_pairs_payload=[
            {"symbol": "EUR/USD"},
            {"symbol": "GBP/USD"},
            {"symbol": "XAU/USD"},
        ]
    )

    result = await TwelveDataForexProvider(lambda: client).discover_supported_provider_symbols()

    assert result == frozenset({"EUR/USD", "GBP/USD", "XAU/USD"})
    assert result <= SUPPORTED_FOREX_PROVIDER_SYMBOLS
    assert client.forex_pairs_calls == 1


async def test_provider_normalizes_latest_prices() -> None:
    client = FakeClient(
        prices={
            "EUR/USD": {"price": "1.08650"},
            "GBP/USD": {"price": "1.27010"},
            "AAPL": {"price": "212.34000"},
        }
    )

    result = await TwelveDataForexProvider(lambda: client).fetch_latest_prices(
        ["EUR/USD", "GBP/USD", "AAPL"]
    )

    assert result.prices == {
        "EUR/USD": Decimal("1.08650"),
        "GBP/USD": Decimal("1.27010"),
        "AAPL": Decimal("212.34000"),
    }
    assert result.unavailable_symbols == frozenset()


@pytest.mark.parametrize("payload", [{"price": "0"}, {"price": "NaN"}, {"status": "error"}, {}])
async def test_provider_marks_invalid_price_payloads_unavailable(payload: object) -> None:
    client = FakeClient(prices={"EUR/USD": payload})

    result = await TwelveDataForexProvider(lambda: client).fetch_latest_prices(["EUR/USD"])

    assert result.prices == {}
    assert result.unavailable_symbols == frozenset({"EUR/USD"})


async def test_provider_marks_unsupported_symbols_unavailable() -> None:
    client = FakeClient(prices={"EUR/USD": {"price": "1.10"}})

    result = await TwelveDataForexProvider(lambda: client).fetch_latest_prices(
        ["EUR/USD", "NZD/USD"]
    )

    assert result.prices == {"EUR/USD": Decimal("1.10")}
    assert result.unavailable_symbols == frozenset({"NZD/USD"})


async def test_provider_normalizes_time_series_candles() -> None:
    client = FakeClient(time_series_payload=(candle_row(),))
    provider = TwelveDataForexProvider(lambda: client)

    candles = await provider.fetch_candles(
        EUR,
        "1m",
        "1m",
        START,
        START + timedelta(minutes=1),
        1,
    )

    assert client.time_series_calls == [
        {
            "symbol": "EUR/USD",
            "interval": "1min",
            "start_date": "2026-06-22 00:00:00",
            "end_date": "2026-06-22 00:00:00",
            "timezone": "UTC",
            "order": "ASC",
            "outputsize": 1,
        }
    ]
    assert candles[0].symbol == "EUR/USD"
    assert candles[0].open == Decimal("1.1000")
    assert candles[0].close_time == START + timedelta(minutes=1) - timedelta(milliseconds=1)
    assert candles[0].volume == Decimal("0")
    assert candles[0].complete is False


@pytest.mark.parametrize(
    ("provider_interval", "expected_interval", "duration"),
    [
        ("1m", "1min", timedelta(minutes=1)),
        ("5m", "5min", timedelta(minutes=5)),
        ("15m", "15min", timedelta(minutes=15)),
        ("1h", "1h", timedelta(hours=1)),
        ("1d", "1day", timedelta(days=1)),
    ],
)
async def test_provider_maps_all_supported_candle_intervals(
    provider_interval: str,
    expected_interval: str,
    duration: timedelta,
) -> None:
    client = FakeClient(time_series_payload=(candle_row(),))
    provider = TwelveDataForexProvider(lambda: client)

    await provider.fetch_candles(
        EUR,
        provider_interval,
        provider_interval,
        START,
        START + duration,
        1,
    )

    assert client.time_series_calls[0]["interval"] == expected_interval
    assert client.time_series_calls[0]["start_date"] == "2026-06-22 00:00:00"
    assert client.time_series_calls[0]["end_date"] == "2026-06-22 00:00:00"
    assert client.time_series_calls[0]["timezone"] == "UTC"
    assert client.time_series_calls[0]["order"] == "ASC"
    assert client.time_series_calls[0]["outputsize"] == 1


@pytest.mark.parametrize("volume", [None, pytest.param("missing", id="omitted")])
async def test_provider_normalizes_absent_volume_to_zero(volume: object) -> None:
    row = candle_row()
    if volume == "missing":
        row.pop("volume")
    else:
        row["volume"] = volume
    provider = TwelveDataForexProvider(lambda: FakeClient(time_series_payload=(row,)))

    candles = await provider.fetch_candles(
        EUR,
        "1m",
        "1m",
        START,
        START + timedelta(minutes=1),
        1,
    )

    assert candles[0].volume == Decimal("0")


@pytest.mark.parametrize("volume", ["bad", "-1", "NaN"])
async def test_provider_rejects_malformed_supplied_volume(volume: str) -> None:
    row = candle_row()
    row["volume"] = volume
    provider = TwelveDataForexProvider(lambda: FakeClient(time_series_payload=(row,)))

    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_candles(
            EUR,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )


async def test_provider_excludes_rows_outside_half_open_range() -> None:
    payload = (
        candle_row(START - timedelta(minutes=1)),
        candle_row(START),
        candle_row(START + timedelta(minutes=1)),
    )
    provider = TwelveDataForexProvider(lambda: FakeClient(time_series_payload=payload))

    candles = await provider.fetch_candles(
        EUR,
        "1m",
        "1m",
        START,
        START + timedelta(minutes=1),
        1,
    )

    assert [candle.open_time for candle in candles] == [START]


async def test_provider_preserves_empty_forex_market_gap() -> None:
    provider = TwelveDataForexProvider(lambda: FakeClient(time_series_payload=()))

    candles = await provider.fetch_candles(
        EUR,
        "1m",
        "1m",
        START,
        START + timedelta(minutes=5),
        5,
    )

    assert candles == []


async def test_provider_discards_closed_session_rows_and_keeps_boundaries() -> None:
    friday_before_close = datetime(2026, 6, 19, 20, 0, tzinfo=UTC)
    friday_close = datetime(2026, 6, 19, 21, 0, tzinfo=UTC)
    sunday_reopen = datetime(2026, 6, 21, 21, 0, tzinfo=UTC)
    provider = TwelveDataForexProvider(
        lambda: FakeClient(
            time_series_payload=(
                candle_row(friday_before_close),
                candle_row(friday_close),
                candle_row(sunday_reopen),
            )
        )
    )

    candles = await provider.fetch_candles(
        EUR,
        "1h",
        "1h",
        friday_before_close,
        sunday_reopen + timedelta(hours=1),
        50,
    )

    assert [candle.open_time for candle in candles] == [
        friday_before_close,
        sunday_reopen,
    ]


async def test_provider_filters_weekend_daily_labels() -> None:
    friday = datetime(2026, 6, 19, tzinfo=UTC)
    saturday = datetime(2026, 6, 20, tzinfo=UTC)
    sunday = datetime(2026, 6, 21, tzinfo=UTC)
    monday = datetime(2026, 6, 22, tzinfo=UTC)
    provider = TwelveDataForexProvider(
        lambda: FakeClient(
            time_series_payload=tuple(
                candle_row(value) for value in (friday, saturday, sunday, monday)
            )
        )
    )

    candles = await provider.fetch_candles(
        EUR,
        "1d",
        "1d",
        friday,
        monday + timedelta(days=1),
        4,
    )

    assert [candle.open_time for candle in candles] == [friday, monday]


@pytest.mark.parametrize(
    "payload",
    [
        "bad",
        ({"datetime": "bad", "open": "1", "high": "1", "low": "1", "close": "1"},),
        (
            {
                "datetime": "2026-06-22 00:00:00",
                "open": "NaN",
                "high": "1",
                "low": "1",
                "close": "1",
            },
        ),
        (candle_row(), candle_row()),
    ],
)
async def test_provider_rejects_invalid_time_series_payloads(payload: object) -> None:
    provider = TwelveDataForexProvider(lambda: FakeClient(time_series_payload=payload))

    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_candles(EUR, "1m", "1m", START, START + timedelta(minutes=1), 1)


async def test_cancelled_twelvedata_candle_call_propagates() -> None:
    started = threading.Event()
    release = threading.Event()

    class BlockingClient(FakeClient):
        def time_series(self, **defaults: object) -> FakeEndpoint:
            self.time_series_calls.append(defaults)
            started.set()
            release.wait(timeout=1)
            return FakeEndpoint((candle_row(),))

    task = asyncio.create_task(
        TwelveDataForexProvider(lambda: BlockingClient()).fetch_candles(
            EUR,
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


async def test_provider_maps_twelvedata_failures_to_provider_unavailable() -> None:
    provider = TwelveDataForexProvider(lambda: FakeClient(error=TwelveDataError("secret detail")))

    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_latest_prices(["EUR/USD"])


async def test_slow_twelvedata_call_does_not_block_event_loop() -> None:
    started = threading.Event()
    release = threading.Event()

    class SlowClient(FakeClient):
        def price(self, **defaults: object) -> FakeEndpoint:
            self.price_calls.append(cast(str, defaults["symbol"]))
            started.set()
            release.wait(timeout=1)
            return FakeEndpoint({"price": "1.10"})

    task = asyncio.create_task(
        TwelveDataForexProvider(lambda: SlowClient()).fetch_latest_prices(["EUR/USD"])
    )
    while not started.is_set():
        await asyncio.sleep(0)

    loop_progressed = False
    await asyncio.sleep(0)
    loop_progressed = True
    release.set()
    result = await task

    assert loop_progressed
    assert result.prices == {"EUR/USD": Decimal("1.10")}


async def test_concurrent_twelvedata_calls_are_serialized() -> None:
    first_started = threading.Event()
    release_first = threading.Event()

    class SerializedClient(FakeClient):
        def price(self, **defaults: object) -> FakeEndpoint:
            self.price_calls.append(cast(str, defaults["symbol"]))
            if len(self.price_calls) == 1:
                first_started.set()
                release_first.wait(timeout=1)
            return FakeEndpoint({"price": "1.10"})

    client = SerializedClient()
    provider = TwelveDataForexProvider(lambda: client)
    first = asyncio.create_task(provider.fetch_latest_prices(["EUR/USD"]))
    while not first_started.is_set():
        await asyncio.sleep(0)
    second = asyncio.create_task(provider.fetch_latest_prices(["GBP/USD"]))
    await asyncio.sleep(0.02)

    assert client.price_calls == ["EUR/USD"]
    release_first.set()
    await asyncio.gather(first, second)
    assert client.price_calls == ["EUR/USD", "GBP/USD"]


async def test_provider_factory_lazily_configures_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    client = FakeClient(prices={"EUR/USD": {"price": "1.10"}})

    class FakeTDClient:
        def __init__(
            self,
            apikey: str,
            base_url: str,
            http_client: object,
        ) -> None:
            captured["apikey"] = apikey
            captured["base_url"] = base_url
            captured["http_client"] = http_client

        def price(self, **defaults: object) -> FakeEndpoint:
            return client.price(**defaults)

        def time_series(self, **defaults: object) -> FakeEndpoint:
            return client.time_series(**defaults)

        def get_forex_pairs_list(self, **defaults: object) -> FakeEndpoint:
            return client.get_forex_pairs_list(**defaults)

    monkeypatch.setattr(twelvedata_module, "TDClient", FakeTDClient)
    provider = build_twelvedata_forex_provider("test-key", "https://example.test/", 2.5)

    result = await provider.fetch_latest_prices(["EUR/USD"])

    assert result.prices == {"EUR/USD": Decimal("1.10")}
    assert captured["apikey"] == "test-key"
    assert captured["base_url"] == "https://example.test"
    assert captured["http_client"].timeout_seconds == 2.5


def test_provider_factory_requires_api_key() -> None:
    with pytest.raises(ProviderUnavailableError):
        build_twelvedata_forex_provider(None, "https://example.test", 1)


def test_twelvedata_sdk_imports_stay_inside_provider_package() -> None:
    root = Path(__file__).parents[2] / "app"
    offenders = []
    for path in root.rglob("*.py"):
        if path.parent.name == "providers":
            continue
        text = path.read_text(encoding="utf-8")
        if "import twelvedata" in text.lower() or "from twelvedata" in text.lower():
            offenders.append(path.relative_to(root))

    assert offenders == []
