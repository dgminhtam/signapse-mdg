import logging
from collections import defaultdict
from decimal import Decimal

from app.core.observability import failure_metadata, log_event
from app.domain.errors import ProviderUnavailableError
from app.domain.quotes import ProviderQuoteBatch, ProviderSymbolQuoteProvider
from app.domain.symbols import SupportedSymbol

logger = logging.getLogger(__name__)


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
                log_event(
                    logger,
                    logging.ERROR,
                    "provider_not_configured",
                    operation="quotes.fetch_latest_prices",
                    provider=provider_name,
                    symbols=provider_symbols,
                    failure_reason="PROVIDER_NOT_CONFIGURED",
                    retryable=False,
                )
                continue
            try:
                batch = await provider.fetch_latest_prices(provider_symbols)
            except ProviderUnavailableError as exc:
                unavailable.update(provider_symbols)
                metadata = failure_metadata(exc)
                log_event(
                    logger,
                    logging.ERROR,
                    "provider_quote_batch_failed",
                    operation="quotes.fetch_latest_prices",
                    provider=provider_name,
                    symbols=provider_symbols,
                    failure_reason=metadata["failure_reason"],
                    retryable=metadata["retryable"],
                )
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
