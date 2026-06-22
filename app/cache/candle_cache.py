import asyncio
from datetime import datetime

from app.domain.candles import Candle


class CandleCache:
    def __init__(self) -> None:
        self._candles: dict[tuple[str, str], Candle] = {}
        self._lock = asyncio.Lock()

    async def get(self, symbol: str, timeframe: str) -> Candle | None:
        async with self._lock:
            return self._candles.get((symbol, timeframe))

    async def put(self, candle: Candle) -> None:
        async with self._lock:
            self._candles[(candle.symbol, candle.timeframe)] = candle

    async def remove(
        self,
        symbol: str,
        timeframe: str,
        *,
        open_time: datetime | None = None,
    ) -> None:
        key = (symbol, timeframe)
        async with self._lock:
            current = self._candles.get(key)
            if current is None:
                return
            if open_time is None or current.open_time == open_time:
                self._candles.pop(key, None)
