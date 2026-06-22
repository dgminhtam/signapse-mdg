from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.cache.candle_cache import CandleCache
from app.domain.candles import Candle

START = datetime(2026, 6, 19, 0, 0, tzinfo=UTC)


def make_candle(open_time: datetime = START, timeframe: str = "1m") -> Candle:
    return Candle(
        "BTC/USD",
        "CRYPTO",
        "BINANCE_SPOT",
        "BTCUSD",
        timeframe,
        open_time,
        open_time + timedelta(minutes=1) - timedelta(milliseconds=1),
        Decimal("10"),
        Decimal("11"),
        Decimal("9"),
        Decimal("10.5"),
        Decimal("1.0"),
        False,
    )


async def test_candle_cache_replaces_and_reads_by_symbol_timeframe() -> None:
    cache = CandleCache()
    first = make_candle(close := START)
    second = make_candle(close + timedelta(minutes=1))

    await cache.put(first)
    await cache.put(second)

    assert await cache.get("BTC/USD", "1m") == second


async def test_candle_cache_remove_can_match_open_time() -> None:
    cache = CandleCache()
    candle = make_candle()
    await cache.put(candle)

    await cache.remove("BTC/USD", "1m", open_time=START + timedelta(minutes=1))
    assert await cache.get("BTC/USD", "1m") == candle

    await cache.remove("BTC/USD", "1m", open_time=START)
    assert await cache.get("BTC/USD", "1m") is None
