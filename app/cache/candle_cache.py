import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from app.domain.candles import Candle

CacheKey = tuple[str, str, str, str]


class CandleCache:
    """Process-local cache for current forming candle snapshots."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 5,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("Candle cache TTL must be positive.")
        self._ttl = timedelta(seconds=ttl_seconds)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._candles: dict[CacheKey, tuple[Candle, datetime]] = {}
        self._key_locks: dict[CacheKey, asyncio.Lock] = {}
        self._lock = asyncio.Lock()

    async def get(
        self,
        symbol: str,
        timeframe: str,
        provider: str | None = None,
        provider_symbol: str | None = None,
        *,
        now: datetime | None = None,
    ) -> Candle | None:
        current_time = now or self._clock()
        async with self._lock:
            if provider is not None and provider_symbol is not None:
                key = (symbol, provider, provider_symbol, timeframe)
                return self._get_valid_locked(key, current_time)
            matches = [
                self._get_valid_locked(key, current_time)
                for key in tuple(self._candles)
                if key[0] == symbol and key[3] == timeframe
            ]
            valid = [candle for candle in matches if candle is not None]
            return valid[0] if len(valid) == 1 else None

    async def put(self, candle: Candle, *, stored_at: datetime | None = None) -> None:
        if candle.complete:
            return
        timestamp = stored_at or self._clock()
        if timestamp >= candle.close_time:
            return
        async with self._lock:
            self._candles[_cache_key(candle)] = (candle, timestamp)

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
                [(symbol, provider, provider_symbol, timeframe)]
                if provider is not None and provider_symbol is not None
                else [key for key in self._candles if key[0] == symbol and key[3] == timeframe]
            )
            for key in keys:
                current = self._candles.get(key)
                if current is not None and (open_time is None or current[0].open_time == open_time):
                    self._candles.pop(key, None)

    @asynccontextmanager
    async def single_flight(
        self,
        symbol: str,
        timeframe: str,
        provider: str,
        provider_symbol: str,
    ) -> AsyncIterator[None]:
        key = (symbol, provider, provider_symbol, timeframe)
        async with self._lock:
            lock = self._key_locks.setdefault(key, asyncio.Lock())
        async with lock:
            yield

    def _get_valid_locked(self, key: CacheKey, now: datetime) -> Candle | None:
        snapshot = self._candles.get(key)
        if snapshot is None:
            return None
        candle, stored_at = snapshot
        if candle.complete or now >= candle.close_time or now - stored_at > self._ttl:
            self._candles.pop(key, None)
            return None
        return candle


def _cache_key(candle: Candle) -> CacheKey:
    return candle.symbol, candle.provider, candle.provider_symbol, candle.timeframe
