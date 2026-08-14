import asyncio
from datetime import datetime

from app.domain.candles import Candle


class CandleCache:
    def __init__(self) -> None:
        self._candles: dict[tuple[str, str, str, str], Candle] = {}
        self._lock = asyncio.Lock()

    async def get(
        self,
        symbol: str,
        timeframe: str,
        provider: str | None = None,
        provider_symbol: str | None = None,
    ) -> Candle | None:
        async with self._lock:
            if provider is not None and provider_symbol is not None:
                return self._candles.get((symbol, provider, provider_symbol, timeframe))
            matches = [
                candle
                for key, candle in self._candles.items()
                if key[0] == symbol and key[3] == timeframe
            ]
            return matches[0] if len(matches) == 1 else None

    async def put(self, candle: Candle) -> None:
        async with self._lock:
            self._candles[_cache_key(candle)] = candle

    async def remove(
        self,
        symbol: str,
        timeframe: str,
        *,
        open_time: datetime | None = None,
        provider: str | None = None,
        provider_symbol: str | None = None,
    ) -> None:
        async with self._lock:
            keys = (
                [
                    (symbol, provider, provider_symbol, timeframe)
                ]
                if provider is not None and provider_symbol is not None
                else [
                    key
                    for key in self._candles
                    if key[0] == symbol and key[3] == timeframe
                ]
            )
            for key in keys:
                current = self._candles.get(key)
                if current is not None and (open_time is None or current.open_time == open_time):
                    self._candles.pop(key, None)


def _cache_key(candle: Candle) -> tuple[str, str, str, str]:
    return candle.symbol, candle.provider, candle.provider_symbol, candle.timeframe
