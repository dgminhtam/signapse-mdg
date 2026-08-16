import asyncio
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol, cast

from requests import Session
from twelvedata import TDClient  # type: ignore[import-untyped]
from twelvedata.exceptions import TwelveDataError  # type: ignore[import-untyped]

from app.core.observability import failure_metadata, log_event, log_failure
from app.domain.candles import Candle
from app.domain.errors import ProviderUnavailableError
from app.domain.market_sessions import get_market_session_policy
from app.domain.quotes import ProviderQuoteBatch
from app.domain.symbols import SupportedSymbol
from app.domain.timeframes import Timeframe, candle_close_time, get_timeframe, last_open_before
from app.providers.normalization import parse_decimal
from app.providers.twelvedata_keys import (
    TwelveDataApiKeyPool,
    TwelveDataKeyUnavailableError,
)

SUPPORTED_TWELVEDATA_PROVIDER_SYMBOLS = frozenset(
    {
        "BTC/USD",
        "ETH/USD",
        "EUR/USD",
        "GBP/USD",
        "USD/JPY",
        "AUD/USD",
        "XAU/USD",
        "AAPL",
        "TSLA",
        "NVDA",
        "MSFT",
        "WTI",
        "SPY",
        "QQQ",
    }
)

_TWELVEDATA_INTERVALS = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1day",
    "1w": "1week",
    "1mo": "1month",
}

logger = logging.getLogger(__name__)


class JsonEndpoint(Protocol):
    def as_json(self) -> object: ...


class TimeSeriesEndpoint(Protocol):
    def as_json(self) -> object: ...


class TwelveDataNoDataError(Exception):
    pass


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
        payload = response.json()
        if _is_no_data_time_series_response(relative_url, payload):
            raise TwelveDataNoDataError
        status_code = _to_int(getattr(response, "status_code", None))
        payload_code = _to_int(payload.get("code")) if isinstance(payload, dict) else None
        if _is_key_related_error(status_code, payload):
            raise TwelveDataKeyUnavailableError(status_code=status_code or payload_code)
        if not response.ok:
            raise TwelveDataError("Twelve Data request failed.")
        if isinstance(payload, dict) and _is_key_related_error(None, payload):
            raise TwelveDataKeyUnavailableError(status_code=payload_code)
        if isinstance(payload, dict) and payload.get("status") == "error":
            raise TwelveDataError("Twelve Data request failed.")
        return response


class TwelveDataMarketDataProvider:
    def __init__(
        self,
        client_factory: Callable[..., TwelveDataClient],
        key_pool: TwelveDataApiKeyPool | None = None,
    ) -> None:
        self._client_factory = client_factory
        self._client: TwelveDataClient | None = None
        self._clients: dict[str, TwelveDataClient] = {}
        self._key_pool = key_pool
        self._client_lock = asyncio.Lock()

    async def discover_supported_provider_symbols(self) -> frozenset[str]:
        try:
            async with self._client_lock:
                payload = await asyncio.to_thread(self._discover_supported_provider_symbols_sync)
        except TwelveDataError as exc:
            log_failure(
                logger,
                "twelvedata_symbol_discovery_failed",
                exc,
                operation="discover_supported_provider_symbols",
                provider="TWELVE_DATA",
            )
            metadata = failure_metadata(exc)
            raise ProviderUnavailableError(
                operation="discover_supported_provider_symbols",
                provider="TWELVE_DATA",
                failure_reason=str(metadata["failure_reason"]),
                retryable=bool(metadata["retryable"]),
            ) from exc
        except Exception as exc:
            log_failure(
                logger,
                "twelvedata_symbol_discovery_failed",
                exc,
                operation="discover_supported_provider_symbols",
                provider="TWELVE_DATA",
            )
            metadata = failure_metadata(exc)
            raise ProviderUnavailableError(
                operation="discover_supported_provider_symbols",
                provider="TWELVE_DATA",
                failure_reason=str(metadata["failure_reason"]),
                retryable=bool(metadata["retryable"]),
            ) from exc
        return payload

    async def fetch_latest_prices(
        self,
        provider_symbols: list[str],
    ) -> ProviderQuoteBatch:
        if not provider_symbols:
            return ProviderQuoteBatch(prices={}, unavailable_symbols=frozenset())
        requested = set(provider_symbols)
        unsupported = requested - SUPPORTED_TWELVEDATA_PROVIDER_SYMBOLS
        try:
            async with self._client_lock:
                prices = await asyncio.to_thread(
                    self._fetch_latest_prices_sync,
                    sorted(requested - unsupported),
                )
        except TwelveDataError as exc:
            log_failure(
                logger,
                "twelvedata_latest_prices_failed",
                exc,
                operation="fetch_latest_prices",
                provider="TWELVE_DATA",
                symbols=provider_symbols,
            )
            metadata = failure_metadata(exc)
            raise ProviderUnavailableError(
                operation="fetch_latest_prices",
                provider="TWELVE_DATA",
                failure_reason=str(metadata["failure_reason"]),
                retryable=bool(metadata["retryable"]),
            ) from exc
        except Exception as exc:
            log_failure(
                logger,
                "twelvedata_latest_prices_failed",
                exc,
                operation="fetch_latest_prices",
                provider="TWELVE_DATA",
                symbols=provider_symbols,
            )
            metadata = failure_metadata(exc)
            raise ProviderUnavailableError(
                operation="fetch_latest_prices",
                provider="TWELVE_DATA",
                failure_reason=str(metadata["failure_reason"]),
                retryable=bool(metadata["retryable"]),
            ) from exc
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
        if symbol.provider_symbol not in SUPPORTED_TWELVEDATA_PROVIDER_SYMBOLS:
            error = ProviderUnavailableError(
                failure_reason="PROVIDER_NOT_CONFIGURED",
                operation="fetch_candles",
                provider="TWELVE_DATA",
                provider_symbol=symbol.provider_symbol,
                symbol=symbol.symbol,
                timeframe=timeframe,
                request_from=start,
                request_to=end,
            )
            log_failure(logger, "twelvedata_provider_not_configured", error)
            raise error
        interval = _TWELVEDATA_INTERVALS.get(provider_interval)
        timeframe_model = get_timeframe(provider_interval)
        if interval is None or timeframe_model is None:
            error = ProviderUnavailableError(
                failure_reason="PROVIDER_NOT_CONFIGURED",
                operation="fetch_candles",
                provider="TWELVE_DATA",
                provider_symbol=symbol.provider_symbol,
                symbol=symbol.symbol,
                timeframe=timeframe,
                request_from=start,
                request_to=end,
            )
            log_failure(logger, "twelvedata_interval_not_configured", error)
            raise error
        try:
            async with self._client_lock:
                payload = await asyncio.to_thread(
                    self._fetch_time_series_sync,
                    symbol.provider_symbol,
                    interval,
                    start,
                    last_open_before(end, timeframe_model),
                    limit,
                )
        except TwelveDataNoDataError:
            log_event(
                logger,
                logging.DEBUG,
                "twelvedata_empty_response",
                operation="fetch_candles",
                provider="TWELVE_DATA",
                provider_symbol=symbol.provider_symbol,
                symbol=symbol.symbol,
                timeframe=timeframe,
                failure_reason="EMPTY_RESPONSE",
                **{"from": start, "to": end},
            )
            return []
        except TwelveDataError as exc:
            log_failure(
                logger,
                "twelvedata_candle_request_failed",
                exc,
                operation="fetch_candles",
                provider="TWELVE_DATA",
                provider_symbol=symbol.provider_symbol,
                symbol=symbol.symbol,
                timeframe=timeframe,
                **{"from": start, "to": end},
            )
            metadata = failure_metadata(exc)
            raise ProviderUnavailableError(
                operation="fetch_candles",
                provider="TWELVE_DATA",
                provider_symbol=symbol.provider_symbol,
                symbol=symbol.symbol,
                timeframe=timeframe,
                request_from=start,
                request_to=end,
                failure_reason=str(metadata["failure_reason"]),
                retryable=bool(metadata["retryable"]),
            ) from exc
        except Exception as exc:
            log_failure(
                logger,
                "twelvedata_candle_request_failed",
                exc,
                operation="fetch_candles",
                provider="TWELVE_DATA",
                provider_symbol=symbol.provider_symbol,
                symbol=symbol.symbol,
                timeframe=timeframe,
                **{"from": start, "to": end},
            )
            metadata = failure_metadata(exc)
            raise ProviderUnavailableError(
                operation="fetch_candles",
                provider="TWELVE_DATA",
                provider_symbol=symbol.provider_symbol,
                symbol=symbol.symbol,
                timeframe=timeframe,
                request_from=start,
                request_to=end,
                failure_reason=str(metadata["failure_reason"]),
                retryable=bool(metadata["retryable"]),
            ) from exc
        try:
            return _normalize_time_series(
                payload=payload,
                symbol=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
                timeframe_model=timeframe_model,
            )
        except ProviderUnavailableError as exc:
            log_failure(
                logger,
                "twelvedata_candle_normalization_failed",
                exc,
                operation="normalize_candles",
                provider="TWELVE_DATA",
                provider_symbol=symbol.provider_symbol,
                symbol=symbol.symbol,
                timeframe=timeframe,
                failure_reason="INVALID_PAYLOAD",
                **{"from": start, "to": end},
            )
            raise

    def _get_client(self, key: str | None = None) -> TwelveDataClient:
        if self._key_pool is None:
            if self._client is None:
                self._client = self._client_factory()
            return self._client
        if key is None:
            raise ProviderUnavailableError(
                failure_reason="PROVIDER_NOT_CONFIGURED",
                operation="get_client",
                provider="TWELVE_DATA",
            )
        client = self._clients.get(key)
        if client is None:
            client = self._client_factory(key)
            self._clients[key] = client
        return client

    def _with_key_retry(self, operation: Callable[[TwelveDataClient], object]) -> object:
        if self._key_pool is None:
            return operation(self._get_client())
        key = self._key_pool.next_key()
        try:
            return operation(self._get_client(key))
        except TwelveDataKeyUnavailableError:
            self._key_pool.cool_down(key)
        alternate = self._key_pool.next_key(exclude=key)
        try:
            return operation(self._get_client(alternate))
        except TwelveDataKeyUnavailableError as exc:
            self._key_pool.cool_down(alternate)
            raise TwelveDataError("Twelve Data request failed.") from exc

    def _discover_supported_provider_symbols_sync(self) -> frozenset[str]:
        payload = self._with_key_retry(lambda client: client.get_forex_pairs_list().as_json())
        discovered = _extract_forex_symbols(payload)
        return discovered & SUPPORTED_TWELVEDATA_PROVIDER_SYMBOLS

    def _fetch_latest_prices_sync(self, provider_symbols: Iterable[str]) -> dict[str, Decimal]:
        def operation(client: TwelveDataClient) -> dict[str, Decimal]:
            prices: dict[str, Decimal] = {}
            for provider_symbol in provider_symbols:
                payload = client.price(symbol=provider_symbol).as_json()
                price = _normalize_price_payload(payload)
                if price is not None:
                    prices[provider_symbol] = price
                else:
                    log_event(
                        logger,
                        logging.DEBUG,
                        "twelvedata_quote_payload_rejected",
                        operation="fetch_latest_price",
                        provider="TWELVE_DATA",
                        provider_symbol=provider_symbol,
                        failure_reason="INVALID_PAYLOAD",
                    )
            return prices

        return cast(dict[str, Decimal], self._with_key_retry(operation))

    def _fetch_time_series_sync(
        self,
        provider_symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> object:
        return self._with_key_retry(
            lambda client: client.time_series(
                symbol=provider_symbol,
                interval=interval,
                start_date=_format_twelvedata_datetime(start),
                end_date=_format_twelvedata_datetime(end),
                timezone="UTC",
                order="ASC",
                outputsize=limit,
            ).as_json()
        )


def build_twelvedata_market_data_provider(
    api_keys: Iterable[str] | str | None,
    base_url: str,
    timeout_seconds: float,
) -> TwelveDataMarketDataProvider:
    effective_keys = _normalize_api_keys(api_keys)
    if not effective_keys:
        error = ProviderUnavailableError(
            failure_reason="PROVIDER_NOT_CONFIGURED",
            operation="build_provider",
            provider="TWELVE_DATA",
        )
        log_failure(logger, "twelvedata_provider_not_configured", error)
        raise error

    normalized_base_url = base_url.rstrip("/")
    timeout = max(timeout_seconds, 0.001)
    key_pool = TwelveDataApiKeyPool(effective_keys)

    def client_factory(api_key: str) -> TwelveDataClient:
        return cast(
            TwelveDataClient,
            TDClient(
                apikey=api_key,
                base_url=normalized_base_url,
                http_client=TwelveDataHttpClient(normalized_base_url, timeout),
            ),
        )

    return TwelveDataMarketDataProvider(client_factory, key_pool)


def _normalize_api_keys(api_keys: Iterable[str] | str | None) -> tuple[str, ...]:
    if api_keys is None:
        return ()
    if isinstance(api_keys, str):
        api_keys = (api_keys,)
    return tuple(dict.fromkeys(api_key.strip() for api_key in api_keys if api_key.strip()))


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
    return parse_decimal(payload.get("price"), positive=True)


def _normalize_time_series(
    payload: object,
    symbol: SupportedSymbol,
    timeframe: str,
    start: datetime,
    end: datetime,
    timeframe_model: Timeframe,
) -> list[Candle]:
    rows = _extract_time_series_rows(payload, symbol.provider_symbol)
    candles: list[Candle] = []
    seen: set[datetime] = set()
    for row in rows:
        open_time = _parse_datetime(row.get("datetime"))
        if open_time is None:
            raise ProviderUnavailableError
        close_time = candle_close_time(open_time, timeframe_model)
        if open_time < start or open_time >= end:
            continue
        if not get_market_session_policy(symbol).is_eligible(open_time, timeframe):
            continue
        if open_time in seen:
            raise ProviderUnavailableError
        open_price = parse_decimal(row.get("open"), positive=True)
        high = parse_decimal(row.get("high"), positive=True)
        low = parse_decimal(row.get("low"), positive=True)
        close = parse_decimal(row.get("close"), positive=True)
        raw_volume = row.get("volume")
        volume = Decimal("0") if raw_volume is None else parse_decimal(raw_volume, positive=False)
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


def _is_no_data_time_series_response(relative_url: str, payload: object) -> bool:
    if "time_series" not in relative_url or not isinstance(payload, dict):
        return False
    message = payload.get("message")
    return (
        payload.get("status") == "error"
        and payload.get("code") == 400
        and isinstance(message, str)
        and message.lower().startswith("no data is available on the specified dates")
    )


def _is_key_related_error(status_code: object, payload: object) -> bool:
    if _to_int(status_code) in {401, 403, 429}:
        return True
    if not isinstance(payload, dict):
        return False
    if _to_int(payload.get("code")) in {401, 403, 429}:
        return True
    message = payload.get("message")
    if not isinstance(message, str):
        return False
    lowered = message.lower()
    return any(token in lowered for token in ("api key", "rate limit", "quota", "credit"))


def _to_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None
