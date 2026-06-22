import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, cast

from requests import Session
from twelvedata import TDClient  # type: ignore[import-untyped]
from twelvedata.exceptions import TwelveDataError  # type: ignore[import-untyped]

from app.domain.candles import Candle
from app.domain.errors import ProviderUnavailableError
from app.domain.market_sessions import get_market_session_policy
from app.domain.quotes import ProviderQuoteBatch
from app.domain.symbols import SupportedSymbol

SUPPORTED_FOREX_PROVIDER_SYMBOLS = frozenset(
    {
        "EUR/USD",
        "GBP/USD",
        "USD/JPY",
        "AUD/USD",
        "XAU/USD",
        "AAPL",
        "TSLA",
        "NVDA",
        "MSFT",
    }
)

_TWELVEDATA_INTERVALS = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "1h": "1h",
    "1d": "1day",
}

_INTERVAL_DURATIONS = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}


class JsonEndpoint(Protocol):
    def as_json(self) -> object: ...


class TimeSeriesEndpoint(Protocol):
    def as_json(self) -> object: ...


class TwelveDataClient(Protocol):
    def price(self, **defaults: object) -> JsonEndpoint: ...

    def time_series(self, **defaults: object) -> TimeSeriesEndpoint: ...

    def get_forex_pairs_list(self, **defaults: object) -> JsonEndpoint: ...


@dataclass(frozen=True, slots=True)
class TwelveDataHttpClient:
    base_url: str
    timeout_seconds: float
    session: Session = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "session", Session())

    def get(self, relative_url: str, *args: Any, **kwargs: Any) -> object:
        params = kwargs.get("params", {})
        if isinstance(params, dict):
            params["source"] = "python"
            kwargs["params"] = params
        response = self.session.get(
            f"{self.base_url}{relative_url}",
            *args,
            timeout=self.timeout_seconds,
            **kwargs,
        )
        if (
            response.headers.get("Is_batch") == "true"
            or response.headers.get("Content-Type") == "text/csv"
        ):
            return response
        if not response.ok:
            raise TwelveDataError("Twelve Data request failed.")
        payload = response.json()
        if isinstance(payload, dict) and payload.get("status") == "error":
            raise TwelveDataError("Twelve Data request failed.")
        return response


class TwelveDataForexProvider:
    def __init__(self, client_factory: Callable[[], TwelveDataClient]) -> None:
        self._client_factory = client_factory
        self._client: TwelveDataClient | None = None
        self._client_lock = asyncio.Lock()

    async def discover_supported_provider_symbols(self) -> frozenset[str]:
        try:
            async with self._client_lock:
                payload = await asyncio.to_thread(self._discover_supported_provider_symbols_sync)
        except TwelveDataError as exc:
            raise ProviderUnavailableError from exc
        except Exception as exc:
            raise ProviderUnavailableError from exc
        return payload

    async def fetch_latest_prices(
        self,
        provider_symbols: list[str],
    ) -> ProviderQuoteBatch:
        if not provider_symbols:
            return ProviderQuoteBatch(prices={}, unavailable_symbols=frozenset())
        requested = set(provider_symbols)
        unsupported = requested - SUPPORTED_FOREX_PROVIDER_SYMBOLS
        try:
            async with self._client_lock:
                prices = await asyncio.to_thread(
                    self._fetch_latest_prices_sync,
                    sorted(requested - unsupported),
                )
        except TwelveDataError as exc:
            raise ProviderUnavailableError from exc
        except Exception as exc:
            raise ProviderUnavailableError from exc
        unavailable = requested - prices.keys()
        return ProviderQuoteBatch(prices=prices, unavailable_symbols=frozenset(unavailable))

    async def fetch_candles(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[Candle]:
        interval = _TWELVEDATA_INTERVALS.get(provider_interval)
        duration = _INTERVAL_DURATIONS.get(provider_interval)
        if interval is None or duration is None:
            raise ProviderUnavailableError
        try:
            async with self._client_lock:
                payload = await asyncio.to_thread(
                    self._fetch_time_series_sync,
                    symbol.provider_symbol,
                    interval,
                    start,
                    end - duration,
                    limit,
                )
        except TwelveDataError as exc:
            raise ProviderUnavailableError from exc
        except Exception as exc:
            raise ProviderUnavailableError from exc
        return _normalize_time_series(
            payload=payload,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            interval_duration=duration,
        )

    def _get_client(self) -> TwelveDataClient:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def _discover_supported_provider_symbols_sync(self) -> frozenset[str]:
        payload = self._get_client().get_forex_pairs_list().as_json()
        discovered = _extract_forex_symbols(payload)
        return discovered & SUPPORTED_FOREX_PROVIDER_SYMBOLS

    def _fetch_latest_prices_sync(self, provider_symbols: Iterable[str]) -> dict[str, Decimal]:
        prices: dict[str, Decimal] = {}
        client = self._get_client()
        for provider_symbol in provider_symbols:
            payload = client.price(symbol=provider_symbol).as_json()
            price = _normalize_price_payload(payload)
            if price is not None:
                prices[provider_symbol] = price
        return prices

    def _fetch_time_series_sync(
        self,
        provider_symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> object:
        return (
            self._get_client()
            .time_series(
                symbol=provider_symbol,
                interval=interval,
                start_date=_format_twelvedata_datetime(start),
                end_date=_format_twelvedata_datetime(end),
                timezone="UTC",
                order="ASC",
                outputsize=limit,
            )
            .as_json()
        )


def build_twelvedata_forex_provider(
    api_key: str | None,
    base_url: str,
    timeout_seconds: float,
) -> TwelveDataForexProvider:
    if api_key is None or not api_key.strip():
        raise ProviderUnavailableError

    normalized_base_url = base_url.rstrip("/")
    timeout = max(timeout_seconds, 0.001)

    def client_factory() -> TwelveDataClient:
        return cast(
            TwelveDataClient,
            TDClient(
                apikey=api_key,
                base_url=normalized_base_url,
                http_client=TwelveDataHttpClient(normalized_base_url, timeout),
            ),
        )

    return TwelveDataForexProvider(client_factory)


def _extract_forex_symbols(payload: object) -> frozenset[str]:
    if not isinstance(payload, list):
        raise ProviderUnavailableError
    symbols: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            raise ProviderUnavailableError
        symbol = item.get("symbol")
        if isinstance(symbol, str):
            symbols.add(symbol)
    return frozenset(symbols)


def _normalize_price_payload(payload: object) -> Decimal | None:
    if not isinstance(payload, dict) or payload.get("status") == "error":
        return None
    return _parse_decimal(payload.get("price"), positive=True)


def _normalize_time_series(
    payload: object,
    symbol: SupportedSymbol,
    timeframe: str,
    start: datetime,
    end: datetime,
    interval_duration: timedelta,
) -> list[Candle]:
    rows = _extract_time_series_rows(payload, symbol.provider_symbol)
    candles: list[Candle] = []
    seen: set[datetime] = set()
    for row in rows:
        open_time = _parse_datetime(row.get("datetime"))
        if open_time is None:
            raise ProviderUnavailableError
        close_time = open_time + interval_duration - timedelta(milliseconds=1)
        if open_time < start or open_time >= end:
            continue
        if not get_market_session_policy(symbol).is_eligible(open_time, timeframe):
            continue
        if open_time in seen:
            raise ProviderUnavailableError
        open_price = _parse_decimal(row.get("open"), positive=True)
        high = _parse_decimal(row.get("high"), positive=True)
        low = _parse_decimal(row.get("low"), positive=True)
        close = _parse_decimal(row.get("close"), positive=True)
        raw_volume = row.get("volume")
        volume = Decimal("0") if raw_volume is None else _parse_decimal(raw_volume, positive=False)
        if None in (open_price, high, low, close, volume):
            raise ProviderUnavailableError
        open_value = cast(Decimal, open_price)
        high_value = cast(Decimal, high)
        low_value = cast(Decimal, low)
        close_value = cast(Decimal, close)
        if high_value < max(open_value, close_value) or low_value > min(open_value, close_value):
            raise ProviderUnavailableError
        seen.add(open_time)
        candles.append(
            Candle(
                symbol=symbol.symbol,
                asset_class=symbol.asset_class,
                provider=symbol.provider,
                provider_symbol=symbol.provider_symbol,
                timeframe=timeframe,
                open_time=open_time,
                close_time=close_time,
                open=open_value,
                high=high_value,
                low=low_value,
                close=close_value,
                volume=cast(Decimal, volume),
                complete=False,
            )
        )
    return sorted(candles, key=lambda candle: candle.open_time)


def _extract_time_series_rows(
    payload: object,
    provider_symbol: str,
) -> tuple[dict[str, object], ...]:
    if isinstance(payload, tuple):
        rows = payload
    elif isinstance(payload, dict) and provider_symbol in payload:
        rows = payload[provider_symbol]
    else:
        raise ProviderUnavailableError
    if not isinstance(rows, tuple):
        raise ProviderUnavailableError
    normalized: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ProviderUnavailableError
        normalized.append(row)
    return tuple(normalized)


def _parse_decimal(value: object, *, positive: bool) -> Decimal | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    if not parsed.is_finite() or parsed < 0 or (positive and parsed <= 0):
        return None
    return parsed


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=UTC)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC)


def _format_twelvedata_datetime(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
