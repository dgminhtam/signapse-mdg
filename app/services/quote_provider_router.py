from collections import defaultdict
from decimal import Decimal

from app.domain.errors import ProviderUnavailableError
from app.domain.quotes import ProviderQuoteBatch, ProviderSymbolQuoteProvider
from app.domain.symbols import SupportedSymbol


class QuoteProviderRouter:
    def __init__(self, providers: dict[str, ProviderSymbolQuoteProvider]) -> None:
        self._providers = providers

    async def fetch_latest_prices(
        self,
        symbols: list[SupportedSymbol],
    ) -> ProviderQuoteBatch:
        if not symbols:
            return ProviderQuoteBatch(prices={}, unavailable_symbols=frozenset())

        prices: dict[str, Decimal] = {}
        unavailable: set[str] = set()
        grouped = _group_by_provider(symbols)

        for provider_name, provider_symbols in grouped.items():
            provider = self._providers.get(provider_name)
            if provider is None:
                unavailable.update(provider_symbols)
                continue
            try:
                batch = await provider.fetch_latest_prices(provider_symbols)
            except ProviderUnavailableError:
                unavailable.update(provider_symbols)
                continue
            prices.update(batch.prices)
            unavailable.update(batch.unavailable_symbols)

        return ProviderQuoteBatch(
            prices=prices,
            unavailable_symbols=frozenset(unavailable),
        )


def _group_by_provider(symbols: list[SupportedSymbol]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for symbol in symbols:
        grouped[symbol.provider].append(symbol.provider_symbol)
    return dict(grouped)
