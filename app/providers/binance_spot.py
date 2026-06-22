import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast, runtime_checkable

from binance_common.configuration import ConfigurationRestAPI
from binance_common.errors import Error
from binance_sdk_spot.rest_api.models import KlinesIntervalEnum
from binance_sdk_spot.spot import Spot

from app.domain.candles import Candle
from app.domain.errors import ProviderUnavailableError
from app.domain.quotes import ProviderQuoteBatch
from app.domain.symbols import SupportedSymbol


@runtime_checkable
class TickerPriceEntry(Protocol):
    symbol: str | None
    price: str | None


class TickerPriceData(Protocol):
    actual_instance: object


class TickerPriceResponse(Protocol):
    def data(self) -> TickerPriceData: ...


class BinanceSpotRestClient(Protocol):
    def ticker_price(
        self,
        symbol: str | None = None,
        symbols: list[str] | None = None,
        symbol_status: object | None = None,
    ) -> TickerPriceResponse: ...

    def klines(
        self,
        symbol: str | None,
        interval: KlinesIntervalEnum | None,
        start_time: int | None = None,
        end_time: int | None = None,
        time_zone: str | None = None,
        limit: int | None = None,
    ) -> object: ...


class BinanceSpotQuoteProvider:
    def __init__(self, client: BinanceSpotRestClient) -> None:
        self._client = client
        self._client_lock = asyncio.Lock()

    async def fetch_latest_prices(
        self,
        provider_symbols: list[str],
    ) -> ProviderQuoteBatch:
        if not provider_symbols:
            return ProviderQuoteBatch(prices={}, unavailable_symbols=frozenset())

        try:
            async with self._client_lock:
                response = await asyncio.to_thread(
                    self._client.ticker_price,
                    symbols=provider_symbols,
                )
            payload = response.data().actual_instance
        except Error as exc:
            raise ProviderUnavailableError from exc
        except Exception as exc:
            raise ProviderUnavailableError from exc

        if not isinstance(payload, list):
            raise ProviderUnavailableError

        requested = set(provider_symbols)
        prices: dict[str, Decimal] = {}
        unavailable: set[str] = set()

        for item in payload:
            if not isinstance(item, TickerPriceEntry):
                continue
            symbol = item.symbol
            if symbol is None or symbol not in requested:
                continue
            if symbol in prices or symbol in unavailable:
                prices.pop(symbol, None)
                unavailable.add(symbol)
                continue
            price = _parse_price(item.price)
            if price is None:
                unavailable.add(symbol)
            else:
                prices[symbol] = price

        unavailable.update(requested - prices.keys())
        return ProviderQuoteBatch(
            prices=prices,
            unavailable_symbols=frozenset(unavailable),
        )


class BinanceSpotCandleProvider:
    def __init__(self, client: BinanceSpotRestClient) -> None:
        self._client = client
        self._client_lock = asyncio.Lock()

    async def fetch_candles(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[Candle]:
        interval = _KLINE_INTERVALS.get(provider_interval)
        if interval is None:
            raise ProviderUnavailableError
        start_ms = _to_milliseconds(start)
        end_ms = _to_milliseconds(end) - 1
        try:
            async with self._client_lock:
                response = await asyncio.to_thread(
                    self._client.klines,
                    symbol=symbol.provider_symbol,
                    interval=interval,
                    start_time=start_ms,
                    end_time=end_ms,
                    time_zone="0",
                    limit=limit,
                )
            data_method = getattr(response, "data", None)
            if not callable(data_method):
                raise ProviderUnavailableError
            payload = data_method()
        except Error as exc:
            raise ProviderUnavailableError from exc
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError from exc
        return _normalize_klines(
            payload=payload,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            interval_duration=_interval_duration(provider_interval),
        )


def build_binance_spot_quote_provider(
    base_url: str,
    timeout_seconds: float,
) -> BinanceSpotQuoteProvider:
    configuration = ConfigurationRestAPI(
        base_path=base_url.rstrip("/"),
        timeout=max(1, round(timeout_seconds * 1000)),
        retries=0,
    )
    sdk = Spot(config_rest_api=configuration)
    return BinanceSpotQuoteProvider(cast(BinanceSpotRestClient, sdk.rest_api))


def build_binance_spot_candle_provider(
    base_url: str,
    timeout_seconds: float,
) -> BinanceSpotCandleProvider:
    configuration = ConfigurationRestAPI(
        base_path=base_url.rstrip("/"),
        timeout=max(1, round(timeout_seconds * 1000)),
        retries=0,
    )
    sdk = Spot(config_rest_api=configuration)
    return BinanceSpotCandleProvider(cast(BinanceSpotRestClient, sdk.rest_api))


def _parse_price(value: object) -> Decimal | None:
    if not isinstance(value, str):
        return None
    try:
        price = Decimal(value)
    except InvalidOperation:
        return None
    if not price.is_finite() or price <= 0:
        return None
    return price


_KLINE_INTERVALS = {
    "1m": KlinesIntervalEnum.INTERVAL_1m,
    "5m": KlinesIntervalEnum.INTERVAL_5m,
    "15m": KlinesIntervalEnum.INTERVAL_15m,
    "1h": KlinesIntervalEnum.INTERVAL_1h,
    "1d": KlinesIntervalEnum.INTERVAL_1d,
}

_INTERVAL_DURATIONS = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}


def _interval_duration(provider_interval: str) -> timedelta:
    try:
        return _INTERVAL_DURATIONS[provider_interval]
    except KeyError as exc:
        raise ProviderUnavailableError from exc


def _to_milliseconds(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _normalize_klines(
    payload: object,
    symbol: SupportedSymbol,
    timeframe: str,
    start: datetime,
    end: datetime,
    interval_duration: timedelta,
) -> list[Candle]:
    if not isinstance(payload, list):
        raise ProviderUnavailableError
    candles: list[Candle] = []
    seen: set[datetime] = set()
    for item in payload:
        if not isinstance(item, list) or len(item) < 7:
            raise ProviderUnavailableError
        open_ms = _parse_milliseconds(item[0])
        close_ms = _parse_milliseconds(item[6])
        if open_ms is None or close_ms is None:
            raise ProviderUnavailableError
        open_time = datetime.fromtimestamp(open_ms / 1000, tz=UTC)
        close_time = datetime.fromtimestamp(close_ms / 1000, tz=UTC)
        expected_close = open_time + interval_duration - timedelta(milliseconds=1)
        if (
            open_time < start
            or open_time >= end
            or close_time != expected_close
            or open_time in seen
        ):
            raise ProviderUnavailableError
        values = [
            _parse_decimal(value, positive=index < 4) for index, value in enumerate(item[1:6])
        ]
        if any(value is None for value in values):
            raise ProviderUnavailableError
        open_price, high, low, close, volume = cast(list[Decimal], values)
        if high < max(open_price, close) or low > min(open_price, close) or high < low:
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
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
                complete=False,
            )
        )
    return sorted(candles, key=lambda candle: candle.open_time)


def _parse_milliseconds(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


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
