import asyncio

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.domain.streams import ProviderStreamEvent


class LifespanProvider:
    def __init__(self) -> None:
        self.events: asyncio.Queue[ProviderStreamEvent] = asyncio.Queue()
        self.subscribe_calls = 0
        self.closed = False

    async def subscribe_quote(self, symbol: object) -> None:
        del symbol
        self.subscribe_calls += 1

    async def subscribe_candle(
        self,
        symbol: object,
        timeframe: str,
        provider_interval: str,
    ) -> None:
        del symbol, timeframe, provider_interval
        self.subscribe_calls += 1

    async def unsubscribe(self, interest: object) -> None:
        del interest

    async def close(self) -> None:
        self.closed = True


def test_lifespan_starts_idle_and_closes_stream_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binance_provider = LifespanProvider()
    twelvedata_provider = LifespanProvider()
    monkeypatch.setattr(
        main_module,
        "build_binance_spot_stream_provider",
        lambda *args: binance_provider,
    )
    monkeypatch.setattr(
        main_module,
        "build_twelvedata_market_data_stream_provider",
        lambda *args, **kwargs: twelvedata_provider,
    )
    application = main_module.create_app()

    with TestClient(application) as client:
        assert client.get("/health").status_code == 200
        assert binance_provider.subscribe_calls == 0
        assert twelvedata_provider.subscribe_calls == 0
        assert application.state.binance_stream_provider is binance_provider
        assert application.state.twelvedata_market_data_stream_provider is twelvedata_provider

    assert binance_provider.closed is True
    assert twelvedata_provider.closed is True
