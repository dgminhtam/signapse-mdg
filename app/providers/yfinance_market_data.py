import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol, cast

import yfinance  # type: ignore[import-untyped]
from yfinance._http import new_session  # type: ignore[import-untyped]

from app.domain.candles import Candle
from app.domain.errors import ProviderUnavailableError
from app.domain.quotes import ProviderQuoteBatch
from app.domain.symbols import SupportedSymbol
from app.domain.timeframes import Timeframe, candle_close_time, get_timeframe
from app.providers.normalization import parse_decimal

SUPPORTED_YFINANCE_PROVIDER_SYMBOLS = frozenset(
    {
        "SI=F",
        "BZ=F",
        "NG=F",
        "KC=F",
        "SB=F",
        "ZW=F",
        "ZC=F",
        "^GSPC",
        "^NDX",
        "^DJI",
    }
)

_YFINANCE_INTERVALS = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "1d": "1d",
    "1w": "1wk",
    "1mo": "1mo",
}

class YFinanceTicker(Protocol):
    def get_info(self) -> dict[str, object]: ...


class YFinanceSession(Protocol):
    request: Callable[..., object]


SessionFactory = Callable[[float], object]
TickerFactory = Callable[[str, object], YFinanceTicker]
DownloadFactory = Callable[..., object]


class YFinanceQuoteProvider:
    def __init__(
        self,
        timeout_seconds: float,
        session_factory: SessionFactory | None = None,
        ticker_factory: TickerFactory | None = None,
        download_factory: DownloadFactory | None = None,
    ) -> None:
        self._timeout_seconds = max(timeout_seconds, 0.001)
        self._session_factory = session_factory or _build_timeout_session
        self._ticker_factory = ticker_factory or _build_ticker
        self._download_factory = download_factory or yfinance.download
        self._session: object | None = None
        self._client_lock = asyncio.Lock()

    async def fetch_latest_prices(
        self,
        provider_symbols: list[str],
    ) -> ProviderQuoteBatch:
        if not provider_symbols:
            return ProviderQuoteBatch(prices={}, unavailable_symbols=frozenset())

        requested = list(dict.fromkeys(provider_symbols))
        supported = [
            symbol for symbol in requested if symbol in SUPPORTED_YFINANCE_PROVIDER_SYMBOLS
        ]
        unavailable = set(requested) - set(supported)

        try:
            async with self._client_lock:
                prices, failed = await asyncio.to_thread(
                    self._fetch_latest_prices_sync,
                    supported,
                )
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError from exc

        unavailable.update(failed)
        return ProviderQuoteBatch(
            prices=prices,
            unavailable_symbols=frozenset(unavailable),
        )

    async def fetch_candles(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[Candle]:
        del limit
        if symbol.provider_symbol not in SUPPORTED_YFINANCE_PROVIDER_SYMBOLS:
            raise ProviderUnavailableError
        interval = _YFINANCE_INTERVALS.get(provider_interval)
        timeframe_model = get_timeframe(provider_interval)
        if interval is None or timeframe_model is None:
            raise ProviderUnavailableError
        try:
            async with self._client_lock:
                payload = await asyncio.to_thread(
                    self._fetch_history_sync,
                    symbol.provider_symbol,
                    interval,
                    start,
                    end,
                )
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError from exc
        return _normalize_history(
            payload=payload,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            timeframe_model=timeframe_model,
        )

    def _fetch_latest_prices_sync(
        self,
        provider_symbols: list[str],
    ) -> tuple[dict[str, Decimal], set[str]]:
        session = self._get_session()
        prices: dict[str, Decimal] = {}
        unavailable: set[str] = set()
        for provider_symbol in provider_symbols:
            try:
                payload = self._ticker_factory(provider_symbol, session).get_info()
                price = _parse_decimal_value(payload.get("regularMarketPrice"), positive=True)
            except Exception:
                unavailable.add(provider_symbol)
                continue
            if price is None:
                unavailable.add(provider_symbol)
            else:
                prices[provider_symbol] = price
        return prices, unavailable

    def _fetch_history_sync(
        self,
        provider_symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> object:
        return self._download_factory(
            tickers=provider_symbol,
            start=start,
            end=end,
            interval=interval,
            timeout=self._timeout_seconds,
            session=self._get_session(),
            threads=False,
            progress=False,
            actions=False,
            auto_adjust=False,
            multi_level_index=False,
        )

    def _get_session(self) -> object:
        if self._session is None:
            try:
                self._session = self._session_factory(self._timeout_seconds)
            except Exception as exc:
                raise ProviderUnavailableError from exc
        return self._session


def build_yfinance_provider(timeout_seconds: float) -> YFinanceQuoteProvider:
    return YFinanceQuoteProvider(timeout_seconds)


def build_yfinance_quote_provider(timeout_seconds: float) -> YFinanceQuoteProvider:
    return build_yfinance_provider(timeout_seconds)


def build_yfinance_candle_provider(timeout_seconds: float) -> YFinanceQuoteProvider:
    return build_yfinance_provider(timeout_seconds)


def _build_ticker(provider_symbol: str, session: object) -> YFinanceTicker:
    return cast(YFinanceTicker, yfinance.Ticker(provider_symbol, session=session))


def _build_timeout_session(timeout_seconds: float) -> object:
    session = new_session()
    _install_timeout(session, timeout_seconds)
    return session


def _install_timeout(session: YFinanceSession, timeout_seconds: float) -> None:
    original_request = session.request

    def request(method: str, url: str, **kwargs: Any) -> object:
        kwargs["timeout"] = timeout_seconds
        return original_request(method, url, **kwargs)

    session.request = request


def _normalize_history(
    payload: object,
    symbol: SupportedSymbol,
    timeframe: str,
    start: datetime,
    end: datetime,
    timeframe_model: Timeframe,
) -> list[Candle]:
    if bool(getattr(payload, "empty", False)):
        return []
    iterrows = getattr(payload, "iterrows", None)
    if not callable(iterrows):
        raise ProviderUnavailableError

    candles: list[Candle] = []
    seen: set[datetime] = set()
    for raw_open_time, row in iterrows():
        open_time = _parse_history_datetime(raw_open_time)
        if open_time is None:
            raise ProviderUnavailableError
        if open_time < start or open_time >= end:
            continue
        if open_time in seen:
            raise ProviderUnavailableError

        open_price = _parse_decimal_value(_row_value(row, "Open"), positive=True)
        high = _parse_decimal_value(_row_value(row, "High"), positive=True)
        low = _parse_decimal_value(_row_value(row, "Low"), positive=True)
        close = _parse_decimal_value(_row_value(row, "Close"), positive=True)
        volume = _parse_volume(_row_value(row, "Volume"))
        if None in (open_price, high, low, close, volume):
            raise ProviderUnavailableError

        open_value = cast(Decimal, open_price)
        high_value = cast(Decimal, high)
        low_value = cast(Decimal, low)
        close_value = cast(Decimal, close)
        if high_value < max(open_value, close_value) or low_value > min(
            open_value,
            close_value,
        ):
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
                close_time=candle_close_time(open_time, timeframe_model),
                open=open_value,
                high=high_value,
                low=low_value,
                close=close_value,
                volume=cast(Decimal, volume),
                complete=False,
            )
        )
    return sorted(candles, key=lambda candle: candle.open_time)


def _row_value(row: object, key: str) -> object:
    getter = getattr(row, "get", None)
    if callable(getter):
        return getter(key)
    if isinstance(row, dict):
        return row.get(key)
    return None


def _parse_history_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        to_pydatetime = getattr(value, "to_pydatetime", None)
        if not callable(to_pydatetime):
            return None
        converted = to_pydatetime()
        if not isinstance(converted, datetime):
            return None
        parsed = converted
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_volume(value: object) -> Decimal | None:
    if _is_missing(value):
        return Decimal("0")
    return _parse_decimal_value(value, positive=False)


def _parse_decimal_value(value: object, *, positive: bool) -> Decimal | None:
    if _is_missing(value):
        return None
    return parse_decimal(value, positive=positive, allow_numbers=True, allow_decimal=True)


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if value.__class__.__name__ in {"NAType", "NaTType"}:
        return True
    try:
        return bool(value != value)
    except Exception:
        return False
