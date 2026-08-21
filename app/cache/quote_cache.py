import asyncio
from collections.abc import Sequence
from datetime import datetime

from app.domain.quotes import Quote
from app.domain.symbols import SupportedSymbol


class QuoteCache:
    def __init__(self) -> None:
        self._quotes: dict[tuple[str, str, str], Quote] = {}
        self._lock = asyncio.Lock()
        self.refresh_lock = asyncio.Lock()

    async def get_many(
        self,
        symbols: Sequence[SupportedSymbol | str],
    ) -> dict[str, Quote]:
        async with self._lock:
            result: dict[str, Quote] = {}
            for symbol in symbols:
                if isinstance(symbol, str):
                    matches = [quote for key, quote in self._quotes.items() if key[0] == symbol]
                    if len(matches) == 1:
                        result[symbol] = matches[0]
                    continue
                quote = self._quotes.get(_cache_key(symbol))
                if quote is not None:
                    result[symbol.symbol] = quote
            return result

    async def put_many(self, quotes: list[Quote]) -> None:
        async with self._lock:
            self._quotes.update({_cache_key(quote): quote for quote in quotes})

    @staticmethod
    def age_seconds(quote: Quote, now: datetime) -> float:
        return max(0.0, (now - quote.received_at).total_seconds())


def _cache_key(value: SupportedSymbol | Quote) -> tuple[str, str, str]:
    return value.symbol, value.provider, value.provider_symbol
