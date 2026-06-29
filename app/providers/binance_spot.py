import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol, cast, runtime_checkable

from binance_common.configuration import ConfigurationRestAPI
from binance_common.errors import Error
from binance_sdk_spot.rest_api.models import KlinesIntervalEnum
from binance_sdk_spot.spot import Spot

from app.domain.candles import Candle
from app.domain.errors import ProviderUnavailableError
from app.domain.quotes import ProviderQuoteBatch
from app.domain.symbols import SupportedSymbol
from app.domain.timeframes import Timeframe, candle_close_time, get_timeframe
from app.providers.normalization import parse_decimal


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
            price = parse_decimal(item.price, positive=True)
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
            timeframe_model=_timeframe_model(provider_interval),
        )


def build_binance_spot_quote_provider(
    base_url: str,
    timeout_seconds: float,
) -> BinanceSpotQuoteProvider:
    return BinanceSpotQuoteProvider(_build_binance_spot_rest_client(base_url, timeout_seconds))


def build_binance_spot_candle_provider(
    base_url: str,
    timeout_seconds: float,
) -> BinanceSpotCandleProvider:
    return BinanceSpotCandleProvider(_build_binance_spot_rest_client(base_url, timeout_seconds))


def _build_binance_spot_rest_client(
    base_url: str,
    timeout_seconds: float,
) -> BinanceSpotRestClient:
    configuration = ConfigurationRestAPI(
        base_path=base_url.rstrip("/"),
        timeout=max(1, round(timeout_seconds * 1000)),
        retries=0,
    )
    sdk = Spot(config_rest_api=configuration)
    return cast(BinanceSpotRestClient, sdk.rest_api)


_KLINE_INTERVALS = {
    "1m": KlinesIntervalEnum.INTERVAL_1m,
    "5m": KlinesIntervalEnum.INTERVAL_5m,
    "15m": KlinesIntervalEnum.INTERVAL_15m,
    "30m": KlinesIntervalEnum.INTERVAL_30m,
    "1h": KlinesIntervalEnum.INTERVAL_1h,
    "1d": KlinesIntervalEnum.INTERVAL_1d,
    "1w": KlinesIntervalEnum.INTERVAL_1w,
    "1mo": KlinesIntervalEnum.INTERVAL_1M,
}


def _timeframe_model(provider_interval: str) -> Timeframe:
    timeframe = get_timeframe(provider_interval)
    if timeframe is None:
        raise ProviderUnavailableError
    return timeframe


def _to_milliseconds(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _normalize_klines(
    payload: object,
    symbol: SupportedSymbol,
    timeframe: str,
    start: datetime,
    end: datetime,
    timeframe_model: Timeframe,
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
        expected_close = candle_close_time(open_time, timeframe_model)
        if (
            open_time < start
            or open_time >= end
            or close_time != expected_close
            or open_time in seen
        ):
            raise ProviderUnavailableError
        values = [
            parse_decimal(value, positive=index < 4) for index, value in enumerate(item[1:6])
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
