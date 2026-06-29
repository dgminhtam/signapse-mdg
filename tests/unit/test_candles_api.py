from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import routes_candles as routes_candles_module
from app.api.routes_candles import (
    get_candle_cache,
    get_candle_provider,
    get_candle_repository,
    get_candle_request_clock,
    get_candle_service,
)
from app.cache.candle_cache import CandleCache
from app.core.config import Settings, get_settings
from app.domain.candles import Candle, CandleRequest, CandleResult
from app.domain.errors import DatabaseUnavailableError, ProviderUnavailableError
from app.domain.symbols import SupportedSymbol
from app.main import app
from app.services.candle_provider_router import CandleProviderRouter

START = datetime(2026, 6, 19, 0, 0, tzinfo=UTC)


class StubCandleService:
    def __init__(
        self,
        result: CandleResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or CandleResult(
            "BTC/USD",
            "1m",
            START,
            START + timedelta(minutes=1),
            [],
        )
        self.error = error
        self.requested: object | None = None

    async def get_candles(self, request: object) -> CandleResult:
        self.requested = request
        if self.error is not None:
            raise self.error
        return self.result


BTC = SupportedSymbol("BTC/USD", "CRYPTO", "TWELVE_DATA", "BTC/USD", True)
EUR = SupportedSymbol("EUR/USD", "FOREX", "TWELVE_DATA", "EUR/USD", True)
WTI = SupportedSymbol("WTI", "COMMODITY", "TWELVE_DATA", "WTI", True)
SPY = SupportedSymbol("SPY", "ETF", "TWELVE_DATA", "SPY", True)
QQQ = SupportedSymbol("QQQ", "ETF", "TWELVE_DATA", "QQQ", True)
YFINANCE_SILVER = SupportedSymbol("XAG/USD", "COMMODITY", "YFINANCE", "SI=F", True)


class FakeCandleRepository:
    def __init__(self, persisted: list[Candle] | None = None) -> None:
        self.persisted = persisted or []
        self.upserted: list[Candle] = []

    async def get_enabled_symbol(self, symbol: str) -> SupportedSymbol | None:
        return {item.symbol: item for item in (BTC, EUR, WTI, SPY, QQQ, YFINANCE_SILVER)}.get(
            symbol
        )

    async def list_complete(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        return [
            candle
            for candle in self.persisted
            if candle.symbol == symbol.symbol
            and candle.timeframe == timeframe
            and start <= candle.open_time < end
        ]

    async def upsert_complete(self, candles: list[Candle]) -> None:
        self.upserted.extend(candles)


class FakeCandleProvider:
    def __init__(self) -> None:
        self.calls: list[SupportedSymbol] = []

    async def fetch_candles(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[Candle]:
        del provider_interval, end, limit
        self.calls.append(symbol)
        return [
            Candle(
                symbol.symbol,
                symbol.asset_class,
                symbol.provider,
                symbol.provider_symbol,
                timeframe,
                start,
                start + timedelta(minutes=1) - timedelta(milliseconds=1),
                Decimal("1.1000"),
                Decimal("1.2000"),
                Decimal("1.0000"),
                Decimal("1.1500"),
                Decimal("0"),
                False,
            )
        ]


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


def valid_params() -> dict[str, str]:
    return {
        "symbol": "BTC/USD",
        "timeframe": "1m",
        "from": "2026-06-19T00:00:00Z",
        "to": "2026-06-19T00:01:00Z",
    }


async def test_candles_serializes_minimal_provider_agnostic_contract(
    client: AsyncClient,
) -> None:
    candle = Candle(
        "BTC/USD",
        "CRYPTO",
        "BINANCE_SPOT",
        "BTCUSD",
        "1m",
        START,
        START + timedelta(minutes=1) - timedelta(milliseconds=1),
        Decimal("10.00"),
        Decimal("11.00"),
        Decimal("9.00"),
        Decimal("10.50"),
        Decimal("0E-8"),
        True,
    )
    app.dependency_overrides[get_candle_service] = lambda: StubCandleService(
        CandleResult(
            "BTC/USD",
            "1m",
            START,
            START + timedelta(minutes=1),
            [candle],
        )
    )

    response = await client.get("/v1/candles", params=valid_params())

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"symbol", "timeframe", "from", "to", "candles"}
    assert set(payload["candles"][0]) == {
        "openTime",
        "closeTime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "complete",
    }
    assert "provider" not in response.text
    assert payload["candles"][0]["close"] == "10.50"
    assert payload["candles"][0]["volume"] == "0.00000000"
    assert payload["candles"][0]["openTime"].endswith("Z")


async def test_candles_returns_empty_series(client: AsyncClient) -> None:
    app.dependency_overrides[get_candle_service] = lambda: StubCandleService()

    response = await client.get("/v1/candles", params=valid_params())

    assert response.status_code == 200
    assert response.json()["candles"] == []


async def test_candles_defaults_omitted_to_and_returns_resolved_boundary(
    client: AsyncClient,
) -> None:
    resolved_to = START + timedelta(minutes=2, seconds=17)
    service = StubCandleService(CandleResult("BTC/USD", "1m", START, resolved_to, []))
    app.dependency_overrides[get_candle_service] = lambda: service
    app.dependency_overrides[get_candle_request_clock] = lambda: lambda: resolved_to

    response = await client.get(
        "/v1/candles",
        params={
            "symbol": "BTC/USD",
            "timeframe": "1m",
            "from": "2026-06-19T00:00:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json()["to"] == "2026-06-19T00:02:17Z"
    assert isinstance(service.requested, CandleRequest)
    assert service.requested.end == resolved_to


async def test_candles_rejects_explicit_empty_to(client: AsyncClient) -> None:
    app.dependency_overrides[get_candle_service] = lambda: StubCandleService()

    response = await client.get(
        "/v1/candles",
        params={
            "symbol": "BTC/USD",
            "timeframe": "1m",
            "from": "2026-06-19T00:00:00Z",
            "to": "",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_TIME_RANGE"


@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({}, "UNSUPPORTED_SYMBOL"),
        ({"symbol": "BTC/USD"}, "UNSUPPORTED_TIMEFRAME"),
        (
            {
                "symbol": "BTC/USD",
                "timeframe": "1m",
                "from": "bad",
                "to": "2026-06-19T00:01:00Z",
            },
            "INVALID_TIME_RANGE",
        ),
    ],
)
async def test_candles_returns_contract_400_not_422(
    client: AsyncClient,
    params: dict[str, str],
    code: str,
) -> None:
    app.dependency_overrides[get_candle_service] = lambda: StubCandleService()

    response = await client.get("/v1/candles", params=params)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == code


async def test_candles_applies_configured_count_limit(client: AsyncClient) -> None:
    app.dependency_overrides[get_candle_service] = lambda: StubCandleService()
    app.dependency_overrides[get_settings] = lambda: Settings(max_candles_per_request=1)
    params = valid_params()
    params["to"] = "2026-06-19T00:02:00Z"

    response = await client.get("/v1/candles", params=params)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_TIME_RANGE"


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (DatabaseUnavailableError("postgresql://secret"), "DATABASE_UNAVAILABLE"),
        (ProviderUnavailableError("raw sdk payload"), "PROVIDER_UNAVAILABLE"),
    ],
)
async def test_candles_sanitizes_service_failures(
    client: AsyncClient,
    error: Exception,
    code: str,
) -> None:
    app.dependency_overrides[get_candle_service] = lambda: StubCandleService(error=error)

    response = await client.get("/v1/candles", params=valid_params())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == code
    assert "secret" not in response.text
    assert "raw sdk payload" not in response.text


@pytest.mark.parametrize(("symbol", "expected"), [("BTC/USD", BTC), ("EUR/USD", EUR)])
async def test_candles_routes_crypto_and_forex_through_fake_twelvedata_provider(
    client: AsyncClient,
    symbol: str,
    expected: SupportedSymbol,
) -> None:
    repository = FakeCandleRepository()
    twelvedata = FakeCandleProvider()
    app.dependency_overrides[get_candle_repository] = lambda: repository
    app.dependency_overrides[get_candle_provider] = lambda: CandleProviderRouter(
        {"TWELVE_DATA": twelvedata}
    )
    app.dependency_overrides[get_candle_cache] = CandleCache

    response = await client.get(
        "/v1/candles",
        params={
            "symbol": symbol,
            "timeframe": "1m",
            "from": "2026-06-22T00:00:00Z",
            "to": "2026-06-22T00:01:00Z",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"symbol", "timeframe", "from", "to", "candles"}
    assert payload["symbol"] == symbol
    assert payload["candles"][0]["volume"] == "0"
    assert set(payload["candles"][0]) == {
        "openTime",
        "closeTime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "complete",
    }
    assert twelvedata.calls == [expected]
    assert repository.upserted[0].provider == "TWELVE_DATA"


async def test_candles_routes_yfinance_through_fake_provider(
    client: AsyncClient,
) -> None:
    repository = FakeCandleRepository()
    yfinance = FakeCandleProvider()
    app.dependency_overrides[get_candle_repository] = lambda: repository
    app.dependency_overrides[get_candle_provider] = lambda: CandleProviderRouter(
        {"YFINANCE": yfinance}
    )
    app.dependency_overrides[get_candle_cache] = CandleCache

    response = await client.get(
        "/v1/candles",
        params={
            "symbol": "XAG/USD",
            "timeframe": "1m",
            "from": "2026-06-22T00:00:00Z",
            "to": "2026-06-22T00:01:00Z",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"symbol", "timeframe", "from", "to", "candles"}
    assert payload["symbol"] == "XAG/USD"
    assert set(payload["candles"][0]) == {
        "openTime",
        "closeTime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "complete",
    }
    assert yfinance.calls == [YFINANCE_SILVER]
    assert repository.upserted[0].provider == "YFINANCE"


async def test_candles_reuse_persisted_yfinance_without_provider_call(
    client: AsyncClient,
) -> None:
    persisted = Candle(
        "XAG/USD",
        "COMMODITY",
        "YFINANCE",
        "SI=F",
        "1m",
        datetime(2026, 6, 22, 0, 0, tzinfo=UTC),
        datetime(2026, 6, 22, 0, 1, tzinfo=UTC) - timedelta(milliseconds=1),
        Decimal("63.00"),
        Decimal("64.00"),
        Decimal("62.00"),
        Decimal("63.50"),
        Decimal("0"),
        True,
    )
    repository = FakeCandleRepository([persisted])
    yfinance = FakeCandleProvider()
    app.dependency_overrides[get_candle_repository] = lambda: repository
    app.dependency_overrides[get_candle_provider] = lambda: CandleProviderRouter(
        {"YFINANCE": yfinance}
    )
    app.dependency_overrides[get_candle_cache] = CandleCache

    response = await client.get(
        "/v1/candles",
        params={
            "symbol": "XAG/USD",
            "timeframe": "1m",
            "from": "2026-06-22T00:00:00Z",
            "to": "2026-06-22T00:01:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json()["candles"][0]["close"] == "63.50"
    assert yfinance.calls == []
    assert repository.upserted == []


async def test_yfinance_provider_failure_is_sanitized(
    client: AsyncClient,
) -> None:
    class FailingProvider(FakeCandleProvider):
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
            raise ProviderUnavailableError("raw yfinance payload")

    app.dependency_overrides[get_candle_repository] = FakeCandleRepository
    app.dependency_overrides[get_candle_provider] = lambda: CandleProviderRouter(
        {"YFINANCE": FailingProvider()}
    )
    app.dependency_overrides[get_candle_cache] = CandleCache

    response = await client.get(
        "/v1/candles",
        params={
            "symbol": "XAG/USD",
            "timeframe": "1m",
            "from": "2026-06-22T00:00:00Z",
            "to": "2026-06-22T00:01:00Z",
        },
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
    assert "raw yfinance payload" not in response.text


@pytest.mark.parametrize(
    ("symbol", "start"),
    [
        ("WTI", "2026-06-22T14:00:00Z"),
        ("SPY", "2026-06-22T14:00:00Z"),
        ("QQQ", "2026-06-22T14:00:00Z"),
    ],
)
async def test_candles_routes_wti_and_etfs_through_twelvedata_provider(
    client: AsyncClient,
    symbol: str,
    start: str,
) -> None:
    repository = FakeCandleRepository()
    twelvedata = FakeCandleProvider()
    app.dependency_overrides[get_candle_repository] = lambda: repository
    app.dependency_overrides[get_candle_provider] = lambda: CandleProviderRouter(
        {"TWELVE_DATA": twelvedata}
    )
    app.dependency_overrides[get_candle_cache] = CandleCache
    start_time = datetime.fromisoformat(start.replace("Z", "+00:00"))

    response = await client.get(
        "/v1/candles",
        params={
            "symbol": symbol,
            "timeframe": "1m",
            "from": start,
            "to": (start_time + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        },
    )

    assert response.status_code == 200
    assert response.json()["symbol"] == symbol
    assert twelvedata.calls[0].symbol == symbol


async def test_candles_returns_200_for_provider_no_data_range(
    client: AsyncClient,
) -> None:
    class EmptyProvider(FakeCandleProvider):
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
            return []

    app.dependency_overrides[get_candle_repository] = FakeCandleRepository
    app.dependency_overrides[get_candle_provider] = lambda: CandleProviderRouter(
        {"TWELVE_DATA": EmptyProvider()}
    )
    app.dependency_overrides[get_candle_cache] = CandleCache

    response = await client.get(
        "/v1/candles",
        params={
            "symbol": "WTI",
            "timeframe": "1h",
            "from": "2026-06-22T13:00:00Z",
            "to": "2026-06-22T14:00:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json()["candles"] == []


async def test_missing_twelvedata_provider_returns_sanitized_503(
    client: AsyncClient,
) -> None:
    app.dependency_overrides[get_candle_repository] = FakeCandleRepository
    app.dependency_overrides[get_candle_provider] = lambda: CandleProviderRouter({})
    app.dependency_overrides[get_candle_cache] = CandleCache

    response = await client.get(
        "/v1/candles",
        params={
            "symbol": "EUR/USD",
            "timeframe": "1m",
            "from": "2026-06-22T00:00:00Z",
            "to": "2026-06-22T00:01:00Z",
        },
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"


async def test_candle_dependency_without_twelvedata_key_keeps_binance_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binance = FakeCandleProvider()
    yfinance = FakeCandleProvider()
    twelvedata_builds = 0

    def fake_twelvedata_builder(
        api_key: str,
        base_url: str,
        timeout_seconds: float,
    ) -> FakeCandleProvider:
        del api_key, base_url, timeout_seconds
        nonlocal twelvedata_builds
        twelvedata_builds += 1
        return FakeCandleProvider()

    monkeypatch.setattr(
        routes_candles_module,
        "get_binance_candle_provider",
        lambda base_url, timeout_seconds: binance,
    )
    monkeypatch.setattr(
        routes_candles_module,
        "get_twelvedata_candle_provider",
        fake_twelvedata_builder,
    )
    monkeypatch.setattr(
        routes_candles_module,
        "get_yfinance_candle_provider",
        lambda timeout_seconds: yfinance,
    )
    provider = get_candle_provider(Settings(twelvedata_api_keys=None))

    candles = await provider.fetch_candles(
        SupportedSymbol("BTC/USD", "CRYPTO", "BINANCE_SPOT", "BTCUSD", True),
        "1m",
        "1m",
        START,
        START + timedelta(minutes=1),
        1,
    )

    assert candles[0].symbol == "BTC/USD"
    assert twelvedata_builds == 0


async def test_candle_dependency_registers_yfinance_without_twelvedata_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    yfinance = FakeCandleProvider()
    monkeypatch.setattr(
        routes_candles_module,
        "get_binance_candle_provider",
        lambda base_url, timeout_seconds: FakeCandleProvider(),
    )
    monkeypatch.setattr(
        routes_candles_module,
        "get_yfinance_candle_provider",
        lambda timeout_seconds: yfinance,
    )

    provider = get_candle_provider(Settings(twelvedata_api_keys=None))

    candles = await provider.fetch_candles(
        YFINANCE_SILVER,
        "1m",
        "1m",
        START,
        START + timedelta(minutes=1),
        1,
    )

    assert candles[0].symbol == "XAG/USD"
    assert yfinance.calls == [YFINANCE_SILVER]
