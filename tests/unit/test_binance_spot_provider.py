import asyncio
import threading
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

import pytest
from binance_common.configuration import ConfigurationRestAPI
from binance_common.errors import NetworkError, TooManyRequestsError

import app.providers.binance_spot as binance_module
from app.domain.errors import ProviderUnavailableError
from app.providers.binance_spot import (
    BinanceSpotQuoteProvider,
    build_binance_spot_quote_provider,
)


@dataclass
class FakeTickerPrice:
    symbol: str | None
    price: str | None


class FakeData:
    def __init__(self, actual_instance: object) -> None:
        self.actual_instance = actual_instance


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def data(self) -> FakeData:
        return FakeData(self._payload)


class FailingResponse:
    def data(self) -> FakeData:
        raise ValueError("invalid generated response")


class FakeSdkClient:
    def __init__(
        self,
        response: object = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[list[str]] = []

    def ticker_price(
        self,
        symbol: str | None = None,
        symbols: list[str] | None = None,
        symbol_status: object | None = None,
    ) -> FakeResponse:
        del symbol, symbol_status
        self.calls.append(symbols or [])
        if self.error is not None:
            raise self.error
        return cast(FakeResponse, self.response)


async def test_provider_fetches_batch_and_normalizes_prices() -> None:
    client = FakeSdkClient(
        FakeResponse(
            [
                FakeTickerPrice("BTCUSD", "62373.79000000"),
                FakeTickerPrice("ETHUSD", "1688.68000000"),
            ]
        )
    )

    result = await BinanceSpotQuoteProvider(client).fetch_latest_prices(["BTCUSD", "ETHUSD"])

    assert result.prices == {
        "BTCUSD": Decimal("62373.79000000"),
        "ETHUSD": Decimal("1688.68000000"),
    }
    assert result.unavailable_symbols == frozenset()
    assert client.calls == [["BTCUSD", "ETHUSD"]]


@pytest.mark.parametrize("bad_price", ["NaN", "Infinity", "0", "-1", "invalid"])
async def test_provider_marks_invalid_price_unavailable(bad_price: str) -> None:
    client = FakeSdkClient(
        FakeResponse(
            [
                FakeTickerPrice("BTCUSD", "10.50"),
                FakeTickerPrice("ETHUSD", bad_price),
            ]
        )
    )

    result = await BinanceSpotQuoteProvider(client).fetch_latest_prices(["BTCUSD", "ETHUSD"])

    assert result.prices == {"BTCUSD": Decimal("10.50")}
    assert result.unavailable_symbols == frozenset({"ETHUSD"})


async def test_provider_marks_duplicate_and_missing_symbols_unavailable() -> None:
    client = FakeSdkClient(
        FakeResponse(
            [
                FakeTickerPrice("BTCUSD", "10"),
                FakeTickerPrice("BTCUSD", "11"),
                FakeTickerPrice("UNREQUESTED", "12"),
            ]
        )
    )

    result = await BinanceSpotQuoteProvider(client).fetch_latest_prices(["BTCUSD", "ETHUSD"])

    assert result.prices == {}
    assert result.unavailable_symbols == frozenset({"BTCUSD", "ETHUSD"})


async def test_provider_rejects_non_batch_sdk_response() -> None:
    client = FakeSdkClient(FakeResponse(FakeTickerPrice("BTCUSD", "10")))

    with pytest.raises(ProviderUnavailableError):
        await BinanceSpotQuoteProvider(client).fetch_latest_prices(["BTCUSD"])


@pytest.mark.parametrize(
    "error",
    [NetworkError("network"), TooManyRequestsError("limited", 429)],
)
async def test_provider_maps_documented_sdk_errors(error: Exception) -> None:
    provider = BinanceSpotQuoteProvider(FakeSdkClient(error=error))

    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_latest_prices(["BTCUSD"])


async def test_provider_maps_response_conversion_failure() -> None:
    provider = BinanceSpotQuoteProvider(FakeSdkClient(FailingResponse()))

    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_latest_prices(["BTCUSD"])


async def test_provider_maps_unexpected_sdk_failure() -> None:
    provider = BinanceSpotQuoteProvider(FakeSdkClient(error=RuntimeError("internal")))

    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_latest_prices(["BTCUSD"])


def test_provider_factory_configures_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    sdk_client = FakeSdkClient(FakeResponse([]))

    class FakeSpot:
        def __init__(self, config_rest_api: object) -> None:
            captured["configuration"] = config_rest_api
            self.rest_api = sdk_client

    monkeypatch.setattr(binance_module, "Spot", FakeSpot)

    provider = build_binance_spot_quote_provider("https://example.test/", 2.5)
    configuration = cast(ConfigurationRestAPI, captured["configuration"])

    assert isinstance(provider, BinanceSpotQuoteProvider)
    assert configuration.base_path == "https://example.test"
    assert configuration.timeout == 2500
    assert configuration.retries == 0
    assert configuration.api_key is None
    assert configuration.api_secret is None


async def test_slow_sdk_call_does_not_block_event_loop() -> None:
    started = threading.Event()
    release = threading.Event()

    class SlowClient(FakeSdkClient):
        def ticker_price(
            self,
            symbol: str | None = None,
            symbols: list[str] | None = None,
            symbol_status: object | None = None,
        ) -> FakeResponse:
            del symbol, symbol_status
            self.calls.append(symbols or [])
            started.set()
            release.wait(timeout=1)
            return FakeResponse([FakeTickerPrice("BTCUSD", "10")])

    task = asyncio.create_task(
        BinanceSpotQuoteProvider(SlowClient()).fetch_latest_prices(["BTCUSD"])
    )
    while not started.is_set():
        await asyncio.sleep(0)

    loop_progressed = False
    await asyncio.sleep(0)
    loop_progressed = True
    release.set()
    result = await task

    assert loop_progressed
    assert result.prices == {"BTCUSD": Decimal("10")}


async def test_concurrent_sdk_calls_are_serialized() -> None:
    first_started = threading.Event()
    release_first = threading.Event()

    class SerializedClient(FakeSdkClient):
        def ticker_price(
            self,
            symbol: str | None = None,
            symbols: list[str] | None = None,
            symbol_status: object | None = None,
        ) -> FakeResponse:
            del symbol, symbol_status
            self.calls.append(symbols or [])
            if len(self.calls) == 1:
                first_started.set()
                release_first.wait(timeout=1)
            provider_symbol = (symbols or ["BTCUSD"])[0]
            return FakeResponse([FakeTickerPrice(provider_symbol, "10")])

    client = SerializedClient()
    provider = BinanceSpotQuoteProvider(client)
    first = asyncio.create_task(provider.fetch_latest_prices(["BTCUSD"]))
    while not first_started.is_set():
        await asyncio.sleep(0)
    second = asyncio.create_task(provider.fetch_latest_prices(["ETHUSD"]))
    await asyncio.sleep(0.02)

    assert client.calls == [["BTCUSD"]]
    release_first.set()
    await asyncio.gather(first, second)
    assert client.calls == [["BTCUSD"], ["ETHUSD"]]


async def test_cancellation_propagates() -> None:
    started = threading.Event()
    release = threading.Event()

    class BlockingClient(FakeSdkClient):
        def ticker_price(
            self,
            symbol: str | None = None,
            symbols: list[str] | None = None,
            symbol_status: object | None = None,
        ) -> FakeResponse:
            del symbol, symbols, symbol_status
            started.set()
            release.wait(timeout=1)
            return FakeResponse([FakeTickerPrice("BTCUSD", "10")])

    task = asyncio.create_task(
        BinanceSpotQuoteProvider(BlockingClient()).fetch_latest_prices(["BTCUSD"])
    )
    while not started.is_set():
        await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()
