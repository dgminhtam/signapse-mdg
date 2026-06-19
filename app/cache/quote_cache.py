import asyncio
from datetime import datetime

from app.domain.quotes import Quote


class QuoteCache:
    def __init__(self) -> None:
        self._quotes: dict[str, Quote] = {}
        self._lock = asyncio.Lock()
        self.refresh_lock = asyncio.Lock()

    async def get_many(self, symbols: list[str]) -> dict[str, Quote]:
        async with self._lock:
            return {symbol: self._quotes[symbol] for symbol in symbols if symbol in self._quotes}

    async def put_many(self, quotes: list[Quote]) -> None:
        async with self._lock:
            self._quotes.update({quote.symbol: quote for quote in quotes})

    @staticmethod
    def age_seconds(quote: Quote, now: datetime) -> float:
        return max(0.0, (now - quote.received_at).total_seconds())
