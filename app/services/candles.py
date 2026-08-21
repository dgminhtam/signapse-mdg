from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from math import ceil

from app.cache.candle_cache import CandleCache
from app.core.time import utc_now
from app.domain.candle_schedules import (
    CandleSchedule,
    ProviderFetchSection,
    get_candle_schedule,
)
from app.domain.candles import (
    Candle,
    CandleProvider,
    CandleRepository,
    CandleRequest,
    CandleResult,
)
from app.domain.errors import CandleRequestError, DatabaseUnavailableError, ProviderSelectionError
from app.domain.market_sessions import get_market_session_policy
from app.domain.symbols import SupportedSymbol
from app.domain.timeframes import (
    Timeframe,
    get_timeframe,
    month_opens,
)
from app.services.candle_count import CountQueryExecution
from app.services.provider_selection import resolve_provider_selection

UNSUPPORTED_SYMBOL_MESSAGE = "Symbol is not supported by this gateway."
UNSUPPORTED_TIMEFRAME_MESSAGE = "Timeframe is not supported by this gateway."
INVALID_TIME_RANGE_MESSAGE = "The candle time range is invalid."


def parse_candle_request(
    raw_symbol: str | None,
    raw_timeframe: str | None,
    raw_from: str | None,
    raw_to: str | None,
    raw_limit: str | None = None,
    raw_provider: str | None = None,
    *,
    raw_count: str | None = None,
    raw_before: str | None = None,
    max_candles: int,
    clock: Callable[[], datetime] = utc_now,
) -> CandleRequest:
    if raw_before is not None:
        raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
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
    if raw_limit is not None and raw_count is not None:
        raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
    if raw_count is not None:
        count = _parse_limit(raw_count, max_candles=max_candles)
        if raw_from is not None and raw_to is not None:
            raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
        if raw_from is not None:
            start = _parse_utc(raw_from)
            return CandleRequest(
                symbol=symbol,
                timeframe=timeframe.value,
                start=start,
                end=start,
                count=count,
                count_direction="forward",
                provider=raw_provider,
            )
        end = clock().astimezone(UTC) if raw_to is None else _parse_utc(raw_to)
        return CandleRequest(
            symbol=symbol,
            timeframe=timeframe.value,
            start=end,
            end=end,
            count=count,
            count_direction="backward",
            provider=raw_provider,
        )

    limit = _parse_limit(raw_limit, max_candles=max_candles)
    if limit is not None:
        if raw_from is not None and raw_to is not None:
            raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
        if raw_from is not None:
            start = _parse_utc(raw_from)
            return CandleRequest(
                symbol=symbol,
                timeframe=timeframe.value,
                start=start,
                end=start,
                limit=limit,
                count_direction="forward",
                provider=raw_provider,
            )
        end = clock().astimezone(UTC) if raw_to is None else _parse_utc(raw_to)
        return CandleRequest(
            symbol=symbol,
            timeframe=timeframe.value,
            start=end,
            end=end,
            limit=limit,
            count_direction="backward",
            provider=raw_provider,
        )

    end = clock().astimezone(UTC) if raw_to is None else _parse_utc(raw_to)
    start = _parse_utc(raw_from)
    _validate_range(
        start,
        end,
        timeframe,
        max_candles=max_candles,
    )
    return CandleRequest(
        symbol=symbol,
        timeframe=timeframe.value,
        start=start,
        end=end,
        provider=raw_provider,
    )


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


def _parse_limit(raw_value: str | None, *, max_candles: int) -> int | None:
    if raw_value is None:
        return None
    try:
        limit = int(raw_value.strip())
    except ValueError as exc:
        raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE) from exc
    if limit < 1 or limit > max_candles:
        raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
    return limit


def _validate_range(
    start: datetime,
    end: datetime,
    timeframe: Timeframe,
    *,
    max_candles: int,
) -> None:
    elapsed = end - start
    if elapsed <= timedelta(0) or _conservative_count(start, end, timeframe) > max_candles:
        raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)


class CandleService:
    def __init__(
        self,
        repository: CandleRepository,
        provider: CandleProvider,
        cache: CandleCache | None = None,
        clock: Callable[[], datetime] | None = None,
        max_candles: int = 1000,
        count_scan_budget: int = 10000,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._cache = cache
        self._clock = clock or (lambda: datetime.now(UTC))
        self._max_candles = max_candles
        self._count_scan_budget = count_scan_budget
        self._count_execution = CountQueryExecution(
            repository=repository,
            provider=provider,
            cache=cache,
            clock=self._clock,
            max_candles=max_candles,
            scan_budget=count_scan_budget,
        )

    async def resolve_symbol(
        self,
        symbol_name: str,
        provider: str | None = None,
    ) -> SupportedSymbol:
        symbol = await self._repository.get_enabled_symbol(symbol_name)
        if symbol is None:
            raise CandleRequestError(
                "UNSUPPORTED_SYMBOL",
                UNSUPPORTED_SYMBOL_MESSAGE,
                {"symbol": symbol_name},
            )
        try:
            symbol, _selection = resolve_provider_selection(symbol, provider)
        except ProviderSelectionError as exc:
            if exc.code == "DATABASE_UNAVAILABLE":
                raise DatabaseUnavailableError from exc
            raise CandleRequestError(exc.code, exc.message, exc.details) from exc
        return symbol

    async def get_candles(
        self,
        request: CandleRequest,
        *,
        resolved_symbol: SupportedSymbol | None = None,
    ) -> CandleResult:
        symbol = resolved_symbol or await self.resolve_symbol(request.symbol, request.provider)
        timeframe = get_timeframe(request.timeframe)
        if timeframe is None:
            raise CandleRequestError(
                "UNSUPPORTED_TIMEFRAME",
                UNSUPPORTED_TIMEFRAME_MESSAGE,
                {"timeframe": request.timeframe},
            )
        if self._cache is None:
            return await self._get_candles(request, symbol, timeframe)
        async with self._cache.single_flight(
            request.symbol,
            request.timeframe,
            symbol.provider,
            symbol.provider_symbol,
        ):
            return await self._get_candles(request, symbol, timeframe)

    async def _get_candles(
        self,
        request: CandleRequest,
        symbol: SupportedSymbol,
        timeframe: Timeframe,
    ) -> CandleResult:
        if request.count is not None:
            return await self._get_count_candles(request, symbol, timeframe)
        policy = get_market_session_policy(symbol)
        schedule = get_candle_schedule(symbol, timeframe)
        if request.limit is None:
            expected_opens = schedule.expected_opens(
                request.start,
                request.end,
                policy,
                request.timeframe,
            )
            result_start = request.start
            result_end = request.end
        elif request.count_direction == "forward":
            expected_opens = schedule.next_opens(
                request.start,
                request.limit,
                policy,
                request.timeframe,
            )
            result_start = expected_opens[0] if expected_opens else request.start
            result_end = schedule.end_after(expected_opens[-1]) if expected_opens else request.end
        else:
            expected_opens = schedule.latest_opens(
                request.end,
                request.limit,
                policy,
                request.timeframe,
            )
            result_start = expected_opens[0] if expected_opens else request.end
            result_end = request.end
        if len(expected_opens) > self._max_candles:
            raise CandleRequestError("INVALID_TIME_RANGE", INVALID_TIME_RANGE_MESSAGE)
        persisted = await self._repository.list_complete(
            symbol,
            request.timeframe,
            result_start,
            result_end,
        )
        persisted = [
            candle
            for candle in persisted
            if policy.is_eligible(candle.open_time, request.timeframe)
        ]
        now = self._clock()

        async def fetch_normalized(
            sections: tuple[ProviderFetchSection, ...],
        ) -> list[Candle]:
            fetched: list[Candle] = []
            for section in sections:
                fetched.extend(
                    await self._provider.fetch_candles(
                        symbol=symbol,
                        timeframe=request.timeframe,
                        provider_interval=timeframe.provider_interval,
                        start=section.start,
                        end=section.end,
                        limit=section.expected_count + 1,
                    )
                )
            return [
                replace(candle, complete=candle.close_time <= now)
                for candle in fetched
                if policy.is_eligible(candle.open_time, request.timeframe)
            ]

        async def store_normalized(candles: list[Candle]) -> None:
            await self._repository.upsert_complete(
                [candle for candle in candles if candle.complete]
            )
            if self._cache is not None:
                for candle in candles:
                    if not candle.complete:
                        await self._cache.put(candle, stored_at=now)

        current = (
            await self._cache.get(
                request.symbol,
                request.timeframe,
                symbol.provider,
                symbol.provider_symbol,
                now=now,
            )
            if self._cache is not None
            else None
        )
        cached_opens = (
            {current.open_time}
            if current is not None
            and current.open_time in expected_opens
            and policy.is_eligible(current.open_time, request.timeframe)
            else set()
        )
        gaps = _find_gaps(
            persisted,
            expected_opens,
            schedule,
            available_opens=cached_opens,
        )
        normalized = await fetch_normalized(gaps)
        await store_normalized(normalized)
        merged = {candle.open_time: candle for candle in normalized}
        merged.update({candle.open_time: candle for candle in persisted})
        if (
            current is not None
            and result_start <= current.open_time < result_end
            and policy.is_eligible(current.open_time, request.timeframe)
        ):
            merged.setdefault(current.open_time, current)

        response_opens = set(expected_opens)
        if (
            request.limit == 1
            and request.count_direction != "forward"
            and expected_opens
            and expected_opens[-1] not in merged
        ):
            fallback_opens = schedule.latest_opens(
                expected_opens[0],
                1,
                policy,
                request.timeframe,
            )
            if fallback_opens:
                fallback_open = fallback_opens[-1]
                fallback_end = schedule.end_after(fallback_open)
                fallback_persisted = await self._repository.list_complete(
                    symbol,
                    request.timeframe,
                    fallback_open,
                    fallback_end,
                )
                fallback_persisted = [
                    candle
                    for candle in fallback_persisted
                    if policy.is_eligible(candle.open_time, request.timeframe)
                ]
                fallback_cached_opens = (
                    {fallback_open}
                    if current is not None
                    and current.open_time == fallback_open
                    and policy.is_eligible(current.open_time, request.timeframe)
                    else set()
                )
                fallback_gaps = _find_gaps(
                    fallback_persisted,
                    fallback_opens,
                    schedule,
                    available_opens=fallback_cached_opens,
                )
                fallback_normalized = await fetch_normalized(fallback_gaps)
                await store_normalized(fallback_normalized)
                fallback_merged = {candle.open_time: candle for candle in fallback_normalized}
                fallback_merged.update({candle.open_time: candle for candle in fallback_persisted})
                if (
                    current is not None
                    and current.open_time == fallback_open
                    and policy.is_eligible(current.open_time, request.timeframe)
                ):
                    fallback_merged.setdefault(current.open_time, current)
                merged.update(fallback_merged)
                if fallback_open in merged:
                    response_opens = {fallback_open}

        return CandleResult(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start=result_start,
            end=result_end,
            candles=sorted(
                (candle for open_time, candle in merged.items() if open_time in response_opens),
                key=lambda candle: candle.open_time,
            ),
            price_display_decimals=symbol.price_display_decimals,
        )

    async def _get_count_candles(
        self,
        request: CandleRequest,
        symbol: SupportedSymbol,
        timeframe: Timeframe,
    ) -> CandleResult:
        return await self._count_execution.execute(request, symbol, timeframe)


def _find_gaps(
    persisted: list[Candle],
    expected_opens: tuple[datetime, ...],
    schedule: CandleSchedule,
    *,
    available_opens: set[datetime] | None = None,
) -> tuple[ProviderFetchSection, ...]:
    available = {
        candle.open_time
        for candle in persisted
        if candle.complete and candle.open_time in expected_opens
    }
    if available_opens is not None:
        available.update(available_opens.intersection(expected_opens))
    return schedule.missing_sections(expected_opens, available)


def _conservative_count(start: datetime, end: datetime, timeframe: Timeframe) -> int:
    if timeframe.calendar_month:
        return len(month_opens(start, end))
    return ceil((end - start) / timeframe.duration)
