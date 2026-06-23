import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import app.api.routes_stream as routes_stream
from app.core.config import Settings
from app.domain.errors import DatabaseUnavailableError, ProviderUnavailableError
from app.domain.quotes import Quote
from app.domain.streams import StatusEvent, StreamQuote, StreamRequest
from app.domain.symbols import SupportedSymbol
from app.main import app
from app.services.stream_manager import ClientRegistration

BTC = SupportedSymbol("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True)
ETH = SupportedSymbol("ETH/USD", "CRYPTO", "BINANCE_SPOT", "ETHUSD", True)
EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True)
SILVER = SupportedSymbol("XAG/USD", "COMMODITY", "YFINANCE", "SI=F", True)
NOW = datetime(2026, 6, 19, 10, 30, tzinfo=UTC)


class FakeManager:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.registered: list[tuple[StreamRequest, list[SupportedSymbol]]] = []
        self.unregistered: list[str] = []

    async def register(
        self,
        request: StreamRequest,
        symbols: list[SupportedSymbol],
    ) -> ClientRegistration:
        if self.error is not None:
            raise self.error
        self.registered.append((request, symbols))
        registration = ClientRegistration(
            "client-1",
            request,
            (),
            asyncio.Queue(10),
        )
        registration.queue.put_nowait(
            StatusEvent("CONNECTING", request.symbols, ("quote", "candle"), NOW)
        )
        registration.queue.put_nowait(
            StreamQuote(
                Quote(
                    "BTC/USD",
                    "CRYPTO",
                    "BINANCE_SPOT",
                    "BTCUSD",
                    Decimal("1E-8"),
                    None,
                    None,
                    NOW,
                )
            )
        )
        return registration

    async def unregister(self, client_id: str) -> None:
        self.unregistered.append(client_id)


@pytest.fixture(autouse=True)
def clear_overrides() -> object:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def patch_registry(monkeypatch: pytest.MonkeyPatch, symbols: list[SupportedSymbol]) -> None:
    async def resolve(_: object) -> list[SupportedSymbol]:
        return symbols

    monkeypatch.setattr(routes_stream, "resolve_stream_symbols", resolve)


def patch_manager(monkeypatch: pytest.MonkeyPatch, manager: FakeManager) -> None:
    monkeypatch.setattr(routes_stream, "get_stream_manager", lambda _: manager)


def assert_websocket_closes(path: str) -> WebSocketDisconnect:
    with TestClient(app) as client:
        with client.websocket_connect(path) as ws:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.receive_json()
    return exc_info.value


@pytest.mark.parametrize(
    ("path", "code", "reason"),
    [
        ("/v1/stream?timeframe=1m", 1008, "INVALID_SYMBOLS"),
        ("/v1/stream?symbols=BTC/USD&timeframe=2m", 1008, "UNSUPPORTED_TIMEFRAME"),
    ],
)
def test_stream_route_rejects_invalid_query_shape(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    code: int,
    reason: str,
) -> None:
    patch_registry(monkeypatch, [BTC, ETH])
    patch_manager(monkeypatch, FakeManager())

    disconnect = assert_websocket_closes(path)

    assert disconnect.code == code
    assert disconnect.reason == reason


def test_stream_route_rejects_too_many_symbols(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_registry(monkeypatch, [BTC, ETH])
    patch_manager(monkeypatch, FakeManager())
    monkeypatch.setattr(routes_stream, "get_settings", lambda: Settings(max_quote_symbols=1))

    disconnect = assert_websocket_closes("/v1/stream?symbols=BTC/USD,ETH/USD&timeframe=1m")

    assert disconnect.code == 1008
    assert disconnect.reason == "TOO_MANY_SYMBOLS"


def test_stream_route_rejects_unsupported_symbol_before_provider_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = FakeManager()
    patch_registry(monkeypatch, [BTC])
    patch_manager(monkeypatch, manager)

    disconnect = assert_websocket_closes("/v1/stream?symbols=SOL/USD&timeframe=1m")

    assert disconnect.code == 1008
    assert disconnect.reason == "UNSUPPORTED_SYMBOL"
    assert manager.registered == []


def test_stream_route_rejects_database_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(_: object) -> list[SupportedSymbol]:
        raise DatabaseUnavailableError("postgresql://secret")

    monkeypatch.setattr(routes_stream, "resolve_stream_symbols", fail)
    patch_manager(monkeypatch, FakeManager())

    disconnect = assert_websocket_closes("/v1/stream?symbols=BTC/USD&timeframe=1m")

    assert disconnect.code == 1011
    assert disconnect.reason == "DATABASE_UNAVAILABLE"


def test_stream_route_rejects_provider_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = FakeManager(ProviderUnavailableError("raw provider detail"))
    patch_registry(monkeypatch, [BTC])
    patch_manager(monkeypatch, manager)

    disconnect = assert_websocket_closes("/v1/stream?symbols=BTC/USD&timeframe=1m")

    assert disconnect.code == 1011
    assert disconnect.reason == "PROVIDER_UNAVAILABLE"


def test_stream_route_sends_exact_status_and_quote_events_and_unregisters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = FakeManager()
    patch_registry(monkeypatch, [BTC])
    patch_manager(monkeypatch, manager)

    with TestClient(app) as client:
        with client.websocket_connect("/v1/stream?symbols=BTC/USD,BTC/USD&timeframe=1m") as ws:
            assert ws.receive_json() == {
                "type": "status",
                "state": "CONNECTING",
                "symbols": ["BTC/USD"],
                "channels": ["quote", "candle"],
                "observedAt": "2026-06-19T10:30:00Z",
            }
            assert ws.receive_json() == {
                "type": "quote",
                "symbol": "BTC/USD",
                "price": "0.00000001",
                "receivedAt": "2026-06-19T10:30:00Z",
            }

    assert manager.registered[0][0] == StreamRequest(("BTC/USD",), "1m")
    assert manager.unregistered == ["client-1"]


def test_stream_route_accepts_valid_mixed_provider_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = FakeManager()
    patch_registry(monkeypatch, [BTC, EUR])
    patch_manager(monkeypatch, manager)

    with TestClient(app) as client:
        with client.websocket_connect("/v1/stream?symbols=BTC/USD,EUR/USD&timeframe=1m") as ws:
            assert ws.receive_json()["state"] == "CONNECTING"

    assert manager.registered[0][0] == StreamRequest(("BTC/USD", "EUR/USD"), "1m")
    assert manager.registered[0][1] == [BTC, EUR]


def test_stream_route_accepts_yfinance_and_three_provider_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = FakeManager()
    patch_registry(monkeypatch, [BTC, EUR, SILVER])
    patch_manager(monkeypatch, manager)

    with TestClient(app) as client:
        with client.websocket_connect(
            "/v1/stream?symbols=BTC/USD,EUR/USD,XAG/USD&timeframe=5m"
        ) as ws:
            assert ws.receive_json()["state"] == "CONNECTING"

    assert manager.registered[0][0] == StreamRequest(
        ("BTC/USD", "EUR/USD", "XAG/USD"),
        "5m",
    )
    assert manager.registered[0][1] == [BTC, EUR, SILVER]
