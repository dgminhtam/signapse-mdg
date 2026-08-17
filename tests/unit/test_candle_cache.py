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
    cache = CandleCache(clock=lambda: START)
    first = make_candle(close := START)
    second = make_candle(close + timedelta(minutes=1))

    await cache.put(first)
    await cache.put(second)

    assert await cache.get("BTC/USD", "1m") == second


async def test_candle_cache_remove_can_match_open_time() -> None:
    cache = CandleCache(clock=lambda: START)
    candle = make_candle()
    await cache.put(candle)

    await cache.remove("BTC/USD", "1m", open_time=START + timedelta(minutes=1))
    assert await cache.get("BTC/USD", "1m") == candle

    await cache.remove("BTC/USD", "1m", open_time=START)
    assert await cache.get("BTC/USD", "1m") is None


async def test_candle_cache_expires_entries_after_configured_ttl() -> None:
    current = [START]
    cache = CandleCache(ttl_seconds=5, clock=lambda: current[0])
    candle = make_candle()

    await cache.put(candle)
    current[0] = START + timedelta(seconds=5)
    assert await cache.get("BTC/USD", "1m") == candle

    current[0] += timedelta(milliseconds=1)
    assert await cache.get("BTC/USD", "1m") is None


async def test_candle_cache_defaults_to_five_second_ttl() -> None:
    current = [START]
    cache = CandleCache(clock=lambda: current[0])
    candle = make_candle()

    await cache.put(candle)
    current[0] = START + timedelta(seconds=5, milliseconds=1)

    assert await cache.get("BTC/USD", "1m") is None


async def test_candle_cache_evicts_at_close_time_without_relabeling() -> None:
    current = [START]
    cache = CandleCache(ttl_seconds=120, clock=lambda: current[0])
    candle = make_candle()

    await cache.put(candle)
    current[0] = candle.close_time - timedelta(microseconds=1)
    assert await cache.get("BTC/USD", "1m") == candle

    current[0] = candle.close_time
    assert await cache.get("BTC/USD", "1m") is None


async def test_candle_cache_isolates_provider_and_timeframe_keys() -> None:
    cache = CandleCache(clock=lambda: START)
    yfinance = make_candle().__class__(
        "BTC/USD",
        "CRYPTO",
        "YFINANCE",
        "BTCUSD",
        "1m",
        START,
        START + timedelta(minutes=1) - timedelta(milliseconds=1),
        Decimal("20"),
        Decimal("21"),
        Decimal("19"),
        Decimal("20.5"),
        Decimal("1"),
        False,
    )
    five_minute = make_candle(timeframe="5m").__class__(
        "BTC/USD",
        "CRYPTO",
        "BINANCE_SPOT",
        "BTCUSD",
        "5m",
        START,
        START + timedelta(minutes=5) - timedelta(milliseconds=1),
        Decimal("30"),
        Decimal("31"),
        Decimal("29"),
        Decimal("30.5"),
        Decimal("1"),
        False,
    )

    await cache.put(make_candle())
    await cache.put(yfinance)
    await cache.put(five_minute)

    assert await cache.get("BTC/USD", "1m", "BINANCE_SPOT", "BTCUSD") == make_candle()
    assert await cache.get("BTC/USD", "1m", "YFINANCE", "BTCUSD") == yfinance
    assert await cache.get("BTC/USD", "5m", "BINANCE_SPOT", "BTCUSD") == five_minute
