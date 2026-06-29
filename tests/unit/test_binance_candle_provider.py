import asyncio
import threading
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from binance_common.errors import NetworkError
from binance_sdk_spot.rest_api.models import KlinesIntervalEnum

from app.domain.errors import ProviderUnavailableError
from app.domain.symbols import SupportedSymbol
from app.providers.binance_spot import BinanceSpotCandleProvider, BinanceSpotRestClient

BTC = SupportedSymbol("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True)
START = datetime(2026, 6, 19, 0, 0, tzinfo=UTC)


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def data(self) -> object:
        return self.payload


class FakeKlineClient:
    def __init__(self, payload: object = None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls: list[dict[str, object]] = []

    def klines(
        self,
        symbol: str | None,
        interval: KlinesIntervalEnum | None,
        start_time: int | None = None,
        end_time: int | None = None,
        time_zone: str | None = None,
        limit: int | None = None,
    ) -> FakeResponse:
        self.calls.append(
            {
                "symbol": symbol,
                "interval": interval,
                "start_time": start_time,
                "end_time": end_time,
                "time_zone": time_zone,
                "limit": limit,
            }
        )
        if self.error is not None:
            raise self.error
        return FakeResponse(self.payload)


def kline(open_time: datetime = START, close_time: datetime | None = None) -> list[object]:
    open_ms = int(open_time.timestamp() * 1000)
    close_ms = int(
        (
            close_time
            or open_time + timedelta(minutes=1) - timedelta(milliseconds=1)
        ).timestamp()
        * 1000
    )
    return [
        open_ms,
        "10.00",
        "11.00",
        "9.00",
        "10.50",
        "12.340",
        close_ms,
        "ignored",
    ]


async def test_candle_provider_calls_sdk_and_normalizes_nested_klines() -> None:
    client = FakeKlineClient([kline()])
    provider = BinanceSpotCandleProvider(cast(BinanceSpotRestClient, client))

    candles = await provider.fetch_candles(
        BTC,
        "1m",
        "1m",
        START,
        START + timedelta(minutes=1),
        1,
    )

    assert client.calls == [
        {
            "symbol": "BTCUSD",
            "interval": KlinesIntervalEnum.INTERVAL_1m,
            "start_time": int(START.timestamp() * 1000),
            "end_time": int((START + timedelta(minutes=1)).timestamp() * 1000) - 1,
            "time_zone": "0",
            "limit": 1,
        }
    ]
    assert candles[0].symbol == "BTC/USD"
    assert str(candles[0].close) == "10.50"
    assert candles[0].complete is False


@pytest.mark.parametrize(
    ("provider_interval", "expected"),
    [
        ("1m", KlinesIntervalEnum.INTERVAL_1m),
        ("5m", KlinesIntervalEnum.INTERVAL_5m),
        ("15m", KlinesIntervalEnum.INTERVAL_15m),
        ("30m", KlinesIntervalEnum.INTERVAL_30m),
        ("1h", KlinesIntervalEnum.INTERVAL_1h),
        ("1d", KlinesIntervalEnum.INTERVAL_1d),
        ("1w", KlinesIntervalEnum.INTERVAL_1w),
        ("1mo", KlinesIntervalEnum.INTERVAL_1M),
    ],
)
async def test_candle_provider_maps_supported_intervals(
    provider_interval: str,
    expected: KlinesIntervalEnum,
) -> None:
    client = FakeKlineClient([])
    provider = BinanceSpotCandleProvider(cast(BinanceSpotRestClient, client))

    assert (
        await provider.fetch_candles(
            BTC,
            provider_interval,
            provider_interval,
            START,
            START + timedelta(days=31),
            1,
        )
        == []
    )
    assert client.calls[0]["interval"] == expected


async def test_candle_provider_derives_monthly_close_time_by_calendar_month() -> None:
    open_time = datetime(2026, 2, 1, tzinfo=UTC)
    close_time = datetime(2026, 3, 1, tzinfo=UTC) - timedelta(milliseconds=1)
    provider = BinanceSpotCandleProvider(
        cast(BinanceSpotRestClient, FakeKlineClient([kline(open_time, close_time)]))
    )

    candles = await provider.fetch_candles(
        BTC,
        "1mo",
        "1mo",
        open_time,
        datetime(2026, 3, 1, tzinfo=UTC),
        1,
    )

    assert candles[0].close_time == close_time


@pytest.mark.parametrize(
    "payload",
    [
        "not-a-list",
        [["bad"]],
        [[int(START.timestamp() * 1000), "NaN", "11", "9", "10", "1", 0]],
        [kline(), kline()],
        [kline(START + timedelta(minutes=1))],
    ],
)
async def test_candle_provider_rejects_malformed_duplicate_and_out_of_range_data(
    payload: object,
) -> None:
    provider = BinanceSpotCandleProvider(cast(BinanceSpotRestClient, FakeKlineClient(payload)))

    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_candles(
            BTC,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )


async def test_candle_provider_maps_sdk_errors() -> None:
    provider = BinanceSpotCandleProvider(
        cast(BinanceSpotRestClient, FakeKlineClient(error=NetworkError("network")))
    )

    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_candles(
            BTC,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )


async def test_candle_provider_offloads_slow_sdk_call() -> None:
    started = threading.Event()
    release = threading.Event()

    class SlowClient(FakeKlineClient):
        def klines(
            self,
            symbol: str | None,
            interval: KlinesIntervalEnum | None,
            start_time: int | None = None,
            end_time: int | None = None,
            time_zone: str | None = None,
            limit: int | None = None,
        ) -> FakeResponse:
            del symbol, interval, start_time, end_time, time_zone, limit
            started.set()
            release.wait(timeout=1)
            return FakeResponse([kline()])

    task = asyncio.create_task(
        BinanceSpotCandleProvider(cast(BinanceSpotRestClient, SlowClient())).fetch_candles(
            BTC,
            "1m",
            "1m",
            START,
            START + timedelta(minutes=1),
            1,
        )
    )
    while not started.is_set():
        await asyncio.sleep(0)
    await asyncio.sleep(0)
    release.set()

    assert (await task)[0].open_time == START


async def test_concurrent_candle_sdk_calls_are_serialized() -> None:
    first_started = threading.Event()
    release_first = threading.Event()

    class SerializedClient(FakeKlineClient):
        def klines(
            self,
            symbol: str | None,
            interval: KlinesIntervalEnum | None,
            start_time: int | None = None,
            end_time: int | None = None,
            time_zone: str | None = None,
            limit: int | None = None,
        ) -> FakeResponse:
            del symbol, interval, start_time, end_time, time_zone, limit
            self.calls.append({})
            if len(self.calls) == 1:
                first_started.set()
                release_first.wait(timeout=1)
            return FakeResponse([kline()])

    client = SerializedClient()
    provider = BinanceSpotCandleProvider(cast(BinanceSpotRestClient, client))
    first = asyncio.create_task(
        provider.fetch_candles(BTC, "1m", "1m", START, START + timedelta(minutes=1), 1)
    )
    while not first_started.is_set():
        await asyncio.sleep(0)
    second = asyncio.create_task(
        provider.fetch_candles(BTC, "1m", "1m", START, START + timedelta(minutes=1), 1)
    )
    await asyncio.sleep(0.02)

    assert len(client.calls) == 1
    release_first.set()
    await asyncio.gather(first, second)
    assert len(client.calls) == 2


async def test_candle_provider_propagates_cancellation() -> None:
    started = threading.Event()
    release = threading.Event()

    class BlockingClient(FakeKlineClient):
        def klines(
            self,
            symbol: str | None,
            interval: KlinesIntervalEnum | None,
            start_time: int | None = None,
            end_time: int | None = None,
            time_zone: str | None = None,
            limit: int | None = None,
        ) -> FakeResponse:
            del symbol, interval, start_time, end_time, time_zone, limit
            started.set()
            release.wait(timeout=1)
            return FakeResponse([kline()])

    task = asyncio.create_task(
        BinanceSpotCandleProvider(cast(BinanceSpotRestClient, BlockingClient())).fetch_candles(
            BTC,
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
