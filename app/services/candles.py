from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.cache.candle_cache import CandleCache
from app.domain.candles import (
    Candle,
    CandleProvider,
    CandleRepository,
    CandleRequest,
    CandleResult,
)
from app.domain.errors import CandleRequestError
from app.domain.market_sessions import MarketSessionPolicy, get_market_session_policy
from app.domain.timeframes import (
    Timeframe,
    expected_candle_count,
    get_timeframe,
    is_aligned,
)

UNSUPPORTED_SYMBOL_MESSAGE = "Symbol is not supported by this gateway."
UNSUPPORTED_TIMEFRAME_MESSAGE = "Timeframe is not supported by this gateway."
INVALID_TIME_RANGE_MESSAGE = "The candle time range is invalid."


def parse_candle_request(
    raw_symbol: str | None,
    raw_timeframe: str | None,
    raw_from: str | None,
    raw_to: str | None,
    *,
    max_range_days: int,
    max_candles: int,
) -> CandleRequest:
    symbol = (raw_symbol or "").strip()
    if not symbol:
        raise CandleRequestError(
            "UNSUPPORTED_SYMBOL",
            UNSUPPORTED_SYMBOL_MESSAGE,
            {"symbol": symbol},
        )
    timeframe_value = (raw_timeframe or "").strip()
    timeframe = get_timeframe(timeframe_value)
    if timeframe is None:
        raise CandleRequestError(
            "UNSUPPORTED_TIMEFRAME",
            UNSUPPORTED_TIMEFRAME_MESSAGE,
            {"timeframe": timeframe_value},
        )
    start = _parse_utc(raw_from)
    end = _parse_utc(raw_to)
    _validate_range(
        start,
        end,
        timeframe,
        max_range_days=max_range_days,
        max_candles=max_candles,
    )
    return CandleRequest(symbol=symbol, timeframe=timeframe.value, start=start, end=end)


def _parse_utc(raw_value: str | None) -> datetime:
    if raw_value is None:
        raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
    value = raw_value.strip()
    if not value or not (value.endswith("Z") or value.endswith("+00:00")):
        raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
    return parsed.astimezone(UTC)


def _validate_range(
    start: datetime,
    end: datetime,
    timeframe: Timeframe,
    *,
    max_range_days: int,
    max_candles: int,
) -> None:
    elapsed = end - start
    if (
        elapsed <= timedelta(0)
        or elapsed > timedelta(days=max_range_days)
        or not is_aligned(start, timeframe)
        or not is_aligned(end, timeframe)
        or expected_candle_count(start, end, timeframe) > max_candles
    ):
        raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)


class CandleService:
    def __init__(
        self,
        repository: CandleRepository,
        provider: CandleProvider,
        cache: CandleCache | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._cache = cache
        self._clock = clock or (lambda: datetime.now(UTC))

    async def get_candles(self, request: CandleRequest) -> CandleResult:
        symbol = await self._repository.get_enabled_symbol(request.symbol)
        if symbol is None:
            raise CandleRequestError(
                "UNSUPPORTED_SYMBOL",
                UNSUPPORTED_SYMBOL_MESSAGE,
                {"symbol": request.symbol},
            )
        timeframe = get_timeframe(request.timeframe)
        if timeframe is None:
            raise CandleRequestError(
                "UNSUPPORTED_TIMEFRAME",
                UNSUPPORTED_TIMEFRAME_MESSAGE,
                {"timeframe": request.timeframe},
            )
        policy = get_market_session_policy(symbol)
        persisted = await self._repository.list_complete(
            symbol,
            request.timeframe,
            request.start,
            request.end,
        )
        persisted = [
            candle
            for candle in persisted
            if policy.is_eligible(candle.open_time, request.timeframe)
        ]
        gaps = _find_gaps(
            persisted,
            request.start,
            request.end,
            timeframe.duration,
            policy=policy,
            timeframe=request.timeframe,
        )
        fetched: list[Candle] = []
        for gap_start, gap_end in gaps:
            fetched.extend(
                await self._provider.fetch_candles(
                    symbol=symbol,
                    timeframe=request.timeframe,
                    provider_interval=timeframe.provider_interval,
                    start=gap_start,
                    end=gap_end,
                    limit=expected_candle_count(gap_start, gap_end, timeframe),
                )
            )
        now = self._clock()
        normalized = [
            replace(candle, complete=candle.close_time < now)
            for candle in fetched
            if policy.is_eligible(candle.open_time, request.timeframe)
        ]
        await self._repository.upsert_complete([candle for candle in normalized if candle.complete])
        merged = {candle.open_time: candle for candle in normalized}
        merged.update({candle.open_time: candle for candle in persisted})
        if self._cache is not None:
            current = await self._cache.get(request.symbol, request.timeframe)
            if (
                current is not None
                and request.start <= current.open_time < request.end
                and policy.is_eligible(current.open_time, request.timeframe)
            ):
                merged.setdefault(current.open_time, current)
        return CandleResult(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start=request.start,
            end=request.end,
            candles=sorted(merged.values(), key=lambda candle: candle.open_time),
        )


def _find_gaps(
    persisted: list[Candle],
    start: datetime,
    end: datetime,
    duration: timedelta,
    *,
    policy: MarketSessionPolicy | None = None,
    timeframe: str = "",
) -> list[tuple[datetime, datetime]]:
    available = {
        candle.open_time
        for candle in persisted
        if candle.complete and start <= candle.open_time < end
    }
    gaps: list[tuple[datetime, datetime]] = []
    cursor = start
    gap_start: datetime | None = None
    while cursor < end:
        eligible = policy is None or policy.is_eligible(cursor, timeframe)
        if not eligible and gap_start is not None:
            gaps.append((gap_start, cursor))
            gap_start = None
        elif eligible and cursor not in available and gap_start is None:
            gap_start = cursor
        elif eligible and cursor in available and gap_start is not None:
            gaps.append((gap_start, cursor))
            gap_start = None
        cursor += duration
    if gap_start is not None:
        gaps.append((gap_start, end))
    return gaps
