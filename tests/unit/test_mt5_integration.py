import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.cache.quote_cache import QuoteCache
from app.domain.candle_schedules import get_candle_schedule
from app.domain.candles import Candle, CandleRequest
from app.domain.errors import ProviderUnavailableError
from app.domain.market_sessions import ALWAYS_OPEN_SESSION
from app.domain.mt5_time import from_broker_wall, to_broker_wall
from app.domain.quotes import ProviderQuoteBatch, Quote
from app.domain.streams import StreamQuote
from app.domain.symbols import SupportedSymbol
from app.domain.timeframes import TIMEFRAMES
from app.providers.mt5 import PROVIDER, MT5Provider
from app.services.candles import CandleService
from app.services.quotes import QuoteService


def symbol() -> SupportedSymbol:
    return SupportedSymbol("XAU/USD", "COMMODITY", PROVIDER, "XAUUSD", True, 2)


@pytest.mark.parametrize(
    "raw,utc",
    [
        ("2026-01-05T00:00:00+00:00", "2026-01-04T22:00:00+00:00"),
        ("2026-07-06T00:00:00+00:00", "2026-07-05T21:00:00+00:00"),
        ("2026-11-02T00:00:00+00:00", "2026-11-01T22:00:00+00:00"),
    ],
)
def test_broker_clock_and_daily_boundaries(raw: str, utc: str) -> None:
    opened = datetime.fromisoformat(utc)
    native = datetime.fromisoformat(raw)
    assert from_broker_wall(native) == opened
    assert to_broker_wall(opened) == native
    schedule = get_candle_schedule(symbol(), TIMEFRAMES["1d"])
    assert schedule.expected_opens(
        opened, opened + timedelta(hours=2), ALWAYS_OPEN_SESSION, "1d"
    ) == (opened,)


@pytest.mark.parametrize("raw", ["2026-03-08T09:30:00+00:00", "2026-11-01T08:30:00+00:00"])
def test_ambiguous_dst_timestamp_fails_closed(raw: str) -> None:
    with pytest.raises(ValueError):
        from_broker_wall(datetime.fromisoformat(raw))


def test_native_mt5_week_starts_sunday_instead_of_monday() -> None:
    # Native W1 sample 1793491200 is Sunday 2026-11-01 00:00 broker time.
    opened = from_broker_wall(datetime(2026, 11, 1, tzinfo=UTC))
    schedule = get_candle_schedule(symbol(), TIMEFRAMES["1w"])
    assert schedule.latest_opens(opened + timedelta(days=1), 1, ALWAYS_OPEN_SESSION, "1w") == (
        opened,
    )


def test_nominal_scan_crosses_dst_weekend_for_closed_stock_history() -> None:
    schedule = get_candle_schedule(symbol(), TIMEFRAMES["4h"])
    opens = schedule.latest_opens(
        datetime(2026, 11, 2, 10, tzinfo=UTC), 32, ALWAYS_OPEN_SESSION, "4h"
    )
    assert len(opens) == 32
    assert list(opens) == sorted(set(opens))
    assert all(schedule.end_after(t) > t for t in opens)


async def test_tcp_ingests_without_subscriber_rejects_bad_auth_and_replay(tmp_path: Path) -> None:
    token = tmp_path / "token"
    token.write_text("a" * 64)
    provider = MT5Provider([symbol()], token_file=token, host="127.0.0.1", port=0)
    await provider.start()
    assert provider._server is not None
    port = provider._server.sockets[0].getsockname()[1]
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"HELLO wrong\n")
        await writer.drain()
        assert await asyncio.wait_for(reader.read(), 1) == b""
        writer.close()
        await writer.wait_closed()
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        now = datetime.now(UTC)
        hello = {
            "type": "hello",
            "version": 1,
            "server": "VantageMarkets-Demo",
            "service": True,
            "algoTrading": False,
            "serverTime": int(to_broker_wall(now).timestamp()),
            "utcTime": int(now.timestamp()),
            "symbols": ["XAUUSD"],
        }
        writer.write(b"HELLO " + b"a" * 64 + b"\n" + json.dumps(hello).encode() + b"\n")
        tick = {
            "type": "tick",
            "seq": 1,
            "symbol": "XAUUSD",
            "connected": True,
            "timeMscRaw": int(to_broker_wall(now).timestamp() * 1000),
            "bid": "3900",
            "ask": "3901",
        }
        payload = json.dumps(tick).encode() + b"\n"
        writer.write(payload[:15])
        await writer.drain()
        await asyncio.sleep(0.01)
        writer.write(payload[15:])
        await writer.drain()
        event = await asyncio.wait_for(provider.events.get(), 1)
        assert isinstance(event, StreamQuote)
        assert event.quote.price == Decimal("3900")
        batch = await provider.fetch_latest_prices(["XAUUSD"])
        assert batch.quote_metadata[(PROVIDER, "XAUUSD")].received_at == event.quote.received_at
        # A repeated observation with a new sequence must not acquire a new receipt time.
        tick["seq"] = 2
        writer.write(json.dumps(tick).encode() + b"\n")
        await writer.drain()
        await asyncio.sleep(0.02)
        assert provider.tick_count == 1
        writer.close()
        await writer.wait_closed()
    finally:
        await provider.close()


async def test_rest_snapshot_does_not_refresh_old_quote_time() -> None:
    now = datetime.now(UTC)
    old = Quote(
        "XAU/USD",
        "COMMODITY",
        PROVIDER,
        "XAUUSD",
        Decimal("3900"),
        None,
        now - timedelta(minutes=10),
        now - timedelta(minutes=1),
        freshness_at=now - timedelta(minutes=10),
    )

    class Repo:
        async def list_enabled(self) -> list[SupportedSymbol]:
            return [symbol()]

    class Provider:
        async def fetch_latest_prices(self, symbols: list[SupportedSymbol]) -> ProviderQuoteBatch:
            return ProviderQuoteBatch(
                {"XAUUSD": old.price}, frozenset(), {(PROVIDER, "XAUUSD"): old}
            )

    result = await QuoteService(Repo(), Provider(), QuoteCache(), 10, 30).get_latest_quotes(
        ["XAU/USD"]
    )
    assert not result.quotes
    assert result.errors[0].code == "DATA_STALE"


async def test_count_query_does_not_fetch_years_to_fill_a_weekend_gap() -> None:
    now = datetime(2026, 11, 2, 10, tzinfo=UTC)
    requests = []

    class Repo:
        async def get_enabled_symbol(self, name: str) -> SupportedSymbol:
            return symbol()

        async def list_complete(self, *args: object) -> list[Candle]:
            return []

        async def upsert_complete(self, candles: list[Candle]) -> None:
            pass

    class Provider:
        async def fetch_candles(
            self,
            symbol: SupportedSymbol,
            timeframe: str,
            provider_interval: str,
            start: datetime,
            end: datetime,
            limit: int,
        ) -> list[Candle]:
            requests.append((end - start).days)
            assert (end - start).days <= 32
            schedule = get_candle_schedule(symbol, TIMEFRAMES[timeframe])
            return [
                Candle(
                    symbol.symbol,
                    symbol.asset_class,
                    PROVIDER,
                    "XAUUSD",
                    timeframe,
                    t,
                    schedule.end_after(t) - timedelta(milliseconds=1),
                    Decimal(1),
                    Decimal(1),
                    Decimal(1),
                    Decimal(1),
                    Decimal(0),
                    True,
                )
                for t in schedule.expected_opens(start, end, ALWAYS_OPEN_SESSION, timeframe)
                if to_broker_wall(t).weekday() < 5
            ]

    request = CandleRequest("XAU/USD", "1d", now, now, count=3, count_direction="backward")
    result = await CandleService(Repo(), Provider(), clock=lambda: now).get_candles(request)
    assert len(result.candles) == 3
    assert len(requests) == 2


async def start_fake_feed(tmp_path: Path, timeout: float = 1) -> tuple:
    token = tmp_path / "rpc-token"
    token.write_text("b" * 64)
    provider = MT5Provider(
        [symbol()], token_file=token, host="127.0.0.1", port=0, timeout_seconds=timeout
    )
    await provider.start()
    assert provider._server is not None
    port = provider._server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    now = datetime.now(UTC)
    hello = {
        "type": "hello",
        "version": 1,
        "server": "VantageMarkets-Demo",
        "service": True,
        "algoTrading": False,
        "serverTime": int(to_broker_wall(now).timestamp()),
        "utcTime": int(now.timestamp()),
        "symbols": ["XAUUSD"],
    }
    writer.write(b"HELLO " + b"b" * 64 + b"\n" + json.dumps(hello).encode() + b"\n")
    await writer.drain()
    async with asyncio.timeout(1):
        while provider.connection_count == 0:
            await asyncio.sleep(0.001)
    return provider, reader, writer


async def test_rpc_retries_loading_and_rejects_bad_ohlc(tmp_path: Path) -> None:
    provider, reader, writer = await start_fake_feed(tmp_path)
    start = datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(minutes=3)
    end = start + timedelta(minutes=2)
    try:
        call = asyncio.create_task(provider.fetch_candles(symbol(), "1m", "1m", start, end, 3))
        parts = (await asyncio.wait_for(reader.readline(), 1)).decode().strip().split("\t")
        assert parts[0] == "RATES" and parts[-1] == "128"
        writer.write(
            json.dumps(
                {"type": "rates", "id": parts[1], "status": "LOADING", "error": 4401, "bars": []}
            ).encode()
            + b"\n"
        )
        await writer.drain()
        parts = (await asyncio.wait_for(reader.readline(), 1)).decode().strip().split("\t")
        bar = {
            "timeRaw": int(to_broker_wall(start).timestamp()),
            "o": "10",
            "h": "12",
            "l": "9",
            "c": "11",
            "volume": "0",
        }
        writer.write(
            json.dumps(
                {"type": "rates", "id": parts[1], "status": "OK", "error": 0, "bars": [bar]}
            ).encode()
            + b"\n"
        )
        await writer.drain()
        candles = await call
        assert len(candles) == 1 and candles[0].open_time == start and candles[0].complete
        call = asyncio.create_task(provider.fetch_candles(symbol(), "1m", "1m", start, end, 3))
        parts = (await reader.readline()).decode().strip().split("\t")
        bar["h"] = "1"
        writer.write(
            json.dumps(
                {"type": "rates", "id": parts[1], "status": "OK", "error": 0, "bars": [bar]}
            ).encode()
            + b"\n"
        )
        await writer.drain()
        with pytest.raises(ProviderUnavailableError):
            await call
        assert not provider._pending
    finally:
        writer.close()
        await provider.close()


async def test_rpc_timeout_and_late_reply_cannot_complete_another_request(tmp_path: Path) -> None:
    provider, reader, writer = await start_fake_feed(tmp_path, 0.08)
    start = datetime.now(UTC) - timedelta(hours=1)
    try:
        call = asyncio.create_task(
            provider.fetch_candles(symbol(), "1m", "1m", start, start + timedelta(minutes=1), 2)
        )
        old = (await reader.readline()).decode().strip().split("\t")[1]
        with pytest.raises(ProviderUnavailableError):
            await call
        assert not provider._pending
        call = asyncio.create_task(
            provider.fetch_candles(symbol(), "1m", "1m", start, start + timedelta(minutes=1), 2)
        )
        new = (await reader.readline()).decode().strip().split("\t")[1]
        writer.write(
            json.dumps(
                {"type": "rates", "id": old, "status": "OK", "error": 0, "bars": []}
            ).encode()
            + b"\n"
        )
        await writer.drain()
        await asyncio.sleep(0.01)
        assert not call.done()
        writer.write(
            json.dumps(
                {"type": "rates", "id": new, "status": "OK", "error": 0, "bars": []}
            ).encode()
            + b"\n"
        )
        await writer.drain()
        assert await call == []
    finally:
        writer.close()
        await provider.close()
