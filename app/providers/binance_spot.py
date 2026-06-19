import asyncio
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast, runtime_checkable

from binance_common.configuration import ConfigurationRestAPI
from binance_common.errors import Error
from binance_sdk_spot.spot import Spot

from app.domain.errors import ProviderUnavailableError
from app.domain.quotes import ProviderQuoteBatch


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
