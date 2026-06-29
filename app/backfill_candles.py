import argparse
import asyncio
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, TextIO

from app.core.config import Settings, get_settings
from app.db.repositories import PostgresCandleRepository, PostgresSymbolRepository
from app.db.session import build_session_factory
from app.domain.candles import CandleProvider, CandleRequest, CandleResult
from app.domain.errors import DatabaseUnavailableError
from app.domain.symbols import SupportedSymbol
from app.domain.timeframes import TIMEFRAMES, add_month, get_timeframe
from app.providers.binance_spot import build_binance_spot_candle_provider
from app.providers.twelvedata_market_data import build_twelvedata_market_data_provider
from app.providers.yfinance_market_data import build_yfinance_candle_provider
from app.services.candle_provider_router import CandleProviderRouter
from app.services.candles import CandleService


@dataclass(frozen=True, slots=True)
class BackfillOptions:
    start: datetime
    end: datetime
    timeframes: tuple[str, ...]
    symbols: frozenset[str] | None = None
    providers: frozenset[str] | None = None
    asset_classes: frozenset[str] | None = None


@dataclass(frozen=True, slots=True)
class BackfillChunk:
    symbol: SupportedSymbol
    timeframe: str
    start: datetime
    end: datetime


class BackfillService(Protocol):
    async def get_candles(self, request: CandleRequest) -> CandleResult: ...


def parse_arguments(argv: Sequence[str] | None = None) -> BackfillOptions:
    parser = argparse.ArgumentParser(description="Backfill complete candles into PostgreSQL.")
    parser.add_argument("--from", dest="start", required=True, type=_parse_utc)
    parser.add_argument("--to", dest="end", required=True, type=_parse_utc)
    parser.add_argument("--timeframes", required=True, type=_parse_csv)
    parser.add_argument("--symbols", type=_parse_csv)
    parser.add_argument("--providers", type=_parse_csv_upper)
    parser.add_argument("--asset-classes", type=_parse_csv_upper)
    args = parser.parse_args(argv)

    timeframes = tuple(args.timeframes)
    unsupported = [value for value in timeframes if get_timeframe(value) is None]
    if unsupported:
        parser.error(f"unsupported timeframe: {unsupported[0]}")
    if args.start >= args.end:
        parser.error("--from must be earlier than --to")
    return BackfillOptions(
        start=args.start,
        end=args.end,
        timeframes=timeframes,
        symbols=frozenset(args.symbols) if args.symbols is not None else None,
        providers=frozenset(args.providers) if args.providers is not None else None,
        asset_classes=frozenset(args.asset_classes) if args.asset_classes is not None else None,
    )


def select_symbols(
    enabled: Sequence[SupportedSymbol],
    options: BackfillOptions,
) -> tuple[SupportedSymbol, ...]:
    rows = tuple(enabled)
    if options.symbols is not None:
        by_name = {symbol.symbol: symbol for symbol in rows}
        missing = sorted(options.symbols - by_name.keys())
        if missing:
            raise ValueError(f"unknown or disabled symbol: {missing[0]}")
        rows = tuple(by_name[name] for name in sorted(options.symbols))
    if options.providers is not None:
        rows = tuple(symbol for symbol in rows if symbol.provider in options.providers)
    if options.asset_classes is not None:
        rows = tuple(symbol for symbol in rows if symbol.asset_class in options.asset_classes)
    return rows


def iter_chunks(
    symbol: SupportedSymbol,
    timeframe: str,
    start: datetime,
    end: datetime,
    max_candles: int,
) -> tuple[BackfillChunk, ...]:
    timeframe_model = TIMEFRAMES[timeframe]
    chunks: list[BackfillChunk] = []
    cursor = start
    while cursor < end:
        if timeframe_model.calendar_month:
            chunk_end = min(add_month(cursor, max_candles), end)
        else:
            chunk_end = min(cursor + timeframe_model.duration * max_candles, end)
        chunks.append(BackfillChunk(symbol, timeframe, cursor, chunk_end))
        cursor = chunk_end
    return tuple(chunks)


async def process_backfill(
    *,
    options: BackfillOptions,
    symbols: Sequence[SupportedSymbol],
    service: BackfillService,
    max_candles: int,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    failed = False
    for symbol in symbols:
        for timeframe in options.timeframes:
            for chunk in iter_chunks(symbol, timeframe, options.start, options.end, max_candles):
                try:
                    result = await service.get_candles(
                        CandleRequest(
                            symbol=chunk.symbol.symbol,
                            timeframe=chunk.timeframe,
                            start=chunk.start,
                            end=chunk.end,
                        )
                    )
                except Exception as exc:
                    failed = True
                    print(
                        _format_failure(chunk, exc),
                        file=stderr,
                    )
                    continue
                print(
                    (
                        f"ok symbol={chunk.symbol.symbol} timeframe={chunk.timeframe} "
                        f"from={chunk.start.isoformat()} to={chunk.end.isoformat()} "
                        f"candles={len(result.candles)}"
                    ),
                    file=stdout,
                )
    return 1 if failed else 0


async def run(options: BackfillOptions) -> int:
    settings = get_settings()
    built = build_session_factory(settings)
    if built is None:
        raise DatabaseUnavailableError
    engine, session_factory = built
    try:
        async with session_factory() as session:
            enabled = await PostgresSymbolRepository(session).list_enabled()
        symbols = select_symbols(enabled, options)
        service = CandleService(
            repository=PostgresCandleRepository(session_factory),
            provider=build_candle_provider(settings),
            cache=None,
            max_candles=settings.max_candles_per_request,
        )
        return await process_backfill(
            options=options,
            symbols=symbols,
            service=service,
            max_candles=settings.max_candles_per_request,
        )
    finally:
        await engine.dispose()


def build_candle_provider(settings: Settings) -> CandleProvider:
    providers: dict[str, CandleProvider] = {
        "BINANCE_SPOT": build_binance_spot_candle_provider(
            settings.binance_rest_base_url,
            settings.provider_http_timeout_seconds,
        ),
        "YFINANCE": build_yfinance_candle_provider(settings.provider_http_timeout_seconds),
    }
    if settings.twelvedata_api_key is not None and settings.twelvedata_api_key.strip():
        providers["TWELVE_DATA"] = build_twelvedata_market_data_provider(
            settings.twelvedata_api_key,
            settings.twelvedata_rest_base_url,
            settings.provider_http_timeout_seconds,
        )
    return CandleProviderRouter(providers)


async def main(argv: Sequence[str] | None = None) -> int:
    try:
        options = parse_arguments(argv)
        return await run(options)
    except (DatabaseUnavailableError, ValueError) as exc:
        print(f"error: {exc.__class__.__name__}", file=sys.stderr)
        return 1


def _parse_utc(raw_value: str) -> datetime:
    value = raw_value.strip()
    if not value or not (value.endswith("Z") or value.endswith("+00:00")):
        raise argparse.ArgumentTypeError("must be an explicit UTC datetime")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an ISO-8601 datetime") from exc
    if parsed.utcoffset() != timedelta(0):
        raise argparse.ArgumentTypeError("must be an explicit UTC datetime")
    return parsed.astimezone(UTC)


def _parse_csv(raw_value: str) -> tuple[str, ...]:
    values = tuple(value.strip() for value in raw_value.split(",") if value.strip())
    if not values:
        raise argparse.ArgumentTypeError("must not be empty")
    return tuple(dict.fromkeys(values))


def _parse_csv_upper(raw_value: str) -> tuple[str, ...]:
    return tuple(value.upper() for value in _parse_csv(raw_value))


def _format_failure(chunk: BackfillChunk, exc: Exception) -> str:
    return (
        f"failed symbol={chunk.symbol.symbol} timeframe={chunk.timeframe} "
        f"from={chunk.start.isoformat()} to={chunk.end.isoformat()} "
        f"error={exc.__class__.__name__}"
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
