import logging
from collections.abc import Callable
from datetime import UTC, datetime

from app.cache.quote_cache import QuoteCache
from app.core.observability import failure_metadata, log_event
from app.domain.errors import (
    DatabaseUnavailableError,
    ProviderSelectionError,
    ProviderUnavailableError,
    QuoteRequestError,
)
from app.domain.quotes import Quote, QuoteError, QuoteProvider, QuoteResult
from app.domain.symbols import SupportedSymbol, SymbolRepository
from app.services.provider_selection import resolve_provider_selection

UNSUPPORTED_SYMBOL_MESSAGE = "Symbol is not supported by this gateway."
PROVIDER_UNAVAILABLE_MESSAGE = "The quote provider is temporarily unavailable."
DATA_STALE_MESSAGE = "The latest quote is stale."

logger = logging.getLogger(__name__)


def parse_symbols(raw_symbols: str | None, max_symbols: int) -> list[str]:
    if raw_symbols is None:
        raise QuoteRequestError("INVALID_SYMBOLS", "The symbols query parameter is required.")
    symbols = list(dict.fromkeys(part.strip() for part in raw_symbols.split(",") if part.strip()))
    if not symbols:
        raise QuoteRequestError("INVALID_SYMBOLS", "At least one symbol is required.")
    if len(symbols) > max_symbols:
        raise QuoteRequestError(
            "TOO_MANY_SYMBOLS",
            f"A maximum of {max_symbols} distinct symbols is allowed.",
        )
    return symbols


class QuoteService:
    def __init__(
        self,
        repository: SymbolRepository,
        provider: QuoteProvider,
        cache: QuoteCache,
        cache_ttl_seconds: float,
        stale_after_seconds: float,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds
        self._stale_after_seconds = stale_after_seconds
        self._clock = clock or (lambda: datetime.now(UTC))

    async def get_latest_quotes(
        self,
        requested_symbols: list[str],
        provider: str | None = None,
    ) -> QuoteResult:
        registry = {symbol.symbol: symbol for symbol in await self._repository.list_enabled()}
        supported: list[SupportedSymbol] = []
        errors_by_symbol = {
            symbol: QuoteError(
                symbol=symbol,
                code="UNSUPPORTED_SYMBOL",
                message=UNSUPPORTED_SYMBOL_MESSAGE,
            )
            for symbol in requested_symbols
            if symbol not in registry
        }

        for requested in requested_symbols:
            symbol = registry.get(requested)
            if symbol is None:
                continue
            try:
                selected, _selection = resolve_provider_selection(symbol, provider)
            except ProviderSelectionError as exc:
                if exc.code == "UNSUPPORTED_PROVIDER":
                    errors_by_symbol[requested] = QuoteError(
                        symbol=requested,
                        code=exc.code,
                        message=exc.message,
                    )
                    continue
                raise DatabaseUnavailableError from exc
            supported.append(selected)

        quotes_by_symbol = await self._resolve_supported(supported, errors_by_symbol)
        return QuoteResult(
            quotes=[
                quotes_by_symbol[symbol]
                for symbol in requested_symbols
                if symbol in quotes_by_symbol
            ],
            errors=[
                errors_by_symbol[symbol]
                for symbol in requested_symbols
                if symbol in errors_by_symbol
            ],
            price_display_decimals={
                symbol: registry[symbol].price_display_decimals
                for symbol in requested_symbols
                if symbol in registry
            },
        )

    async def _resolve_supported(
        self,
        supported: list[SupportedSymbol],
        errors: dict[str, QuoteError],
    ) -> dict[str, Quote]:
        if not supported:
            return {}

        now = self._clock()
        cached = await self._cache.get_many(supported)
        resolved = {
            item.symbol: cached[item.symbol]
            for item in supported
            if item.symbol in cached
            and self._cache.age_seconds(cached[item.symbol], now) <= self._cache_ttl_seconds
        }
        pending = [item for item in supported if item.symbol not in resolved]
        if not pending:
            return resolved

        async with self._cache.refresh_lock:
            now = self._clock()
            cached = await self._cache.get_many(pending)
            still_pending: list[SupportedSymbol] = []
            for item in pending:
                quote = cached.get(item.symbol)
                if (
                    quote is not None
                    and self._cache.age_seconds(quote, now) <= self._cache_ttl_seconds
                ):
                    resolved[item.symbol] = quote
                else:
                    still_pending.append(item)

            if still_pending:
                await self._refresh(still_pending, cached, resolved, errors)
        return resolved

    async def _refresh(
        self,
        pending: list[SupportedSymbol],
        cached: dict[str, Quote],
        resolved: dict[str, Quote],
        errors: dict[str, QuoteError],
    ) -> None:
        try:
            batch = await self._provider.fetch_latest_prices(pending)
        except ProviderUnavailableError as exc:
            metadata = failure_metadata(exc)
            log_event(
                logger,
                logging.WARNING,
                "cache_fallback_after_provider_failure",
                operation="quotes.refresh",
                provider="MULTI_PROVIDER",
                symbols=[item.provider_symbol for item in pending],
                count=len(pending),
                failure_reason=metadata["failure_reason"],
                retryable=metadata["retryable"],
            )
            self._use_fallbacks(pending, cached, resolved, errors)
            return

        received_at = self._clock()
        refreshed: list[Quote] = []
        for item in pending:
            price = batch.prices.get(item.provider_symbol)
            if price is None or item.provider_symbol in batch.unavailable_symbols:
                self._use_fallback(item, cached.get(item.symbol), resolved, errors)
                continue
            quote = Quote(
                symbol=item.symbol,
                asset_class=item.asset_class,
                provider=item.provider,
                provider_symbol=item.provider_symbol,
                price=price,
                volume=None,
                provider_time=None,
                received_at=received_at,
            )
            refreshed.append(quote)
            resolved[item.symbol] = quote
        await self._cache.put_many(refreshed)

    def _use_fallbacks(
        self,
        pending: list[SupportedSymbol],
        cached: dict[str, Quote],
        resolved: dict[str, Quote],
        errors: dict[str, QuoteError],
    ) -> None:
        for item in pending:
            self._use_fallback(item, cached.get(item.symbol), resolved, errors)

    def _use_fallback(
        self,
        item: SupportedSymbol,
        cached: Quote | None,
        resolved: dict[str, Quote],
        errors: dict[str, QuoteError],
    ) -> None:
        if (
            cached is not None
            and self._cache.age_seconds(cached, self._clock()) <= self._stale_after_seconds
        ):
            resolved[item.symbol] = cached
            return
        if cached is not None:
            errors[item.symbol] = QuoteError(
                symbol=item.symbol,
                code="DATA_STALE",
                message=DATA_STALE_MESSAGE,
            )
            return
        errors[item.symbol] = QuoteError(
            symbol=item.symbol,
            code="PROVIDER_UNAVAILABLE",
            message=PROVIDER_UNAVAILABLE_MESSAGE,
        )
