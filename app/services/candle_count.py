from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime

from app.cache.candle_cache import CandleCache
from app.core.observability import log_event
from app.domain.candle_schedules import CandleSchedule, get_candle_schedule
from app.domain.candles import Candle, CandleProvider, CandleRepository, CandleRequest, CandleResult
from app.domain.errors import CandleRequestError, DatabaseUnavailableError, ProviderUnavailableError
from app.domain.market_sessions import MarketSessionPolicy, get_market_session_policy
from app.domain.symbols import SupportedSymbol
from app.domain.timeframes import Timeframe

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CountScanPage:
    expected_opens: tuple[datetime, ...]
    start: datetime
    end: datetime


class CountScanCursor:
    def __init__(
        self,
        schedule: CandleSchedule,
        policy: MarketSessionPolicy,
        request: CandleRequest,
        *,
        page_capacity: int,
        scan_budget: int,
    ) -> None:
        self._schedule = schedule
        self._policy = policy
        self._request = request
        self._page_capacity = max(1, page_capacity)
        self._scan_budget = scan_budget
        self._scanned = 0
        self._first_page = True
        self._anchor = request.start if request.count_direction == "forward" else request.end

    @property
    def scanned(self) -> int:
        return self._scanned

    @property
    def exhausted(self) -> bool:
        return self._scanned >= self._scan_budget

    def next_page(self, count: int) -> CountScanPage | None:
        remaining_budget = self._scan_budget - self._scanned
        if remaining_budget <= 0:
            return None
        page_size = min(self._page_capacity, remaining_budget)
        if self._first_page:
            page_size = min(page_size, count)

        if self._request.count_direction == "forward":
            expected_opens = self._schedule.next_opens(
                self._anchor,
                page_size,
                self._policy,
                self._request.timeframe,
            )
        else:
            expected_opens = self._schedule.latest_opens(
                self._anchor,
                page_size,
                self._policy,
                self._request.timeframe,
            )
        if not expected_opens:
            return None

        self._first_page = False
        self._scanned += len(expected_opens)
        page_start = expected_opens[0]
        page_end = self._schedule.end_after(expected_opens[-1])
        self._anchor = page_end if self._request.count_direction == "forward" else page_start
        return CountScanPage(expected_opens, page_start, page_end)


class CountQueryExecution:
    """Resolve provider-backed row counts without materializing the scan budget."""

    def __init__(
        self,
        repository: CandleRepository,
        provider: CandleProvider,
        cache: CandleCache | None,
        *,
        clock: Callable[[], datetime],
        max_candles: int,
        scan_budget: int,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._cache = cache
        self._clock = clock
        self._max_candles = max_candles
        self._scan_budget = scan_budget
        self._page_capacity = max(1, max_candles - 1)

    async def execute(
        self,
        request: CandleRequest,
        symbol: SupportedSymbol,
        timeframe: Timeframe,
    ) -> CandleResult:
        count = request.count
        if count is None or count < 1 or request.count_direction not in {"forward", "backward"}:
            raise CandleRequestError("INVALID_TIME_RANGE", "The candle time range is invalid.")

        policy = get_market_session_policy(symbol)
        schedule = get_candle_schedule(symbol, timeframe)
        cursor = CountScanCursor(
            schedule,
            policy,
            request,
            # Cold broker history must not scan years just to fill a weekend gap.
            page_capacity=(
                min(self._page_capacity, max(32, count * 2))
                if symbol.provider == "MT5_VANTAGE_DEMO"
                else self._page_capacity
            ),
            scan_budget=self._scan_budget,
        )
        now = self._clock()
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

        merged: dict[datetime, Candle] = {}
        result_start = request.start if request.count_direction == "forward" else request.end
        result_end = request.end
        page_count = 0
        provider_call_count = 0
        persisted_rows = 0
        provider_rows = 0
        calendar_ms = 0.0
        database_ms = 0.0
        provider_ms = 0.0
        stop_reason = "error"

        try:
            while len(merged) < count:
                calendar_started = time.perf_counter()
                try:
                    page = await asyncio.to_thread(cursor.next_page, count)
                finally:
                    calendar_ms += (time.perf_counter() - calendar_started) * 1000
                if page is None:
                    break

                page_count += 1
                if request.count_direction == "backward":
                    result_start = page.start
                else:
                    result_end = page.end

                (
                    page_merged,
                    page_provider_calls,
                    page_persisted_rows,
                    page_provider_rows,
                    page_database_ms,
                    page_provider_ms,
                ) = await self._load_page(
                    page,
                    request,
                    symbol,
                    timeframe,
                    policy,
                    current,
                    now,
                )
                provider_call_count += page_provider_calls
                persisted_rows += page_persisted_rows
                provider_rows += page_provider_rows
                database_ms += page_database_ms
                provider_ms += page_provider_ms
                merged.update(page_merged)

            if len(merged) >= count:
                stop_reason = "target"
            elif cursor.exhausted:
                stop_reason = "scan_budget"
            else:
                stop_reason = "history_exhausted"
        except asyncio.CancelledError as exc:
            database_ms += _stage_elapsed(exc, "database")
            provider_ms += _stage_elapsed(exc, "provider")
            stop_reason = "cancelled"
            raise
        except ProviderUnavailableError as exc:
            database_ms += _stage_elapsed(exc, "database")
            provider_ms += _stage_elapsed(exc, "provider")
            stop_reason = "provider_failure"
            raise
        except DatabaseUnavailableError as exc:
            database_ms += _stage_elapsed(exc, "database")
            provider_ms += _stage_elapsed(exc, "provider")
            stop_reason = "database_failure"
            raise
        finally:
            log_event(
                logger,
                logging.INFO,
                "candle_count_completed",
                operation="candles.count",
                provider=symbol.provider,
                provider_symbol=symbol.provider_symbol,
                symbol=request.symbol,
                timeframe=request.timeframe,
                count=count,
                mode="count",
                count_direction=request.count_direction,
                eligible_slots_scanned=cursor.scanned,
                page_count=page_count,
                provider_call_count=provider_call_count,
                persisted_rows=persisted_rows,
                provider_rows=provider_rows,
                returned_rows=min(len(merged), count),
                stop_reason=stop_reason,
                calendar_ms=round(calendar_ms, 3),
                db_ms=round(database_ms, 3),
                provider_ms=round(provider_ms, 3),
            )

        ordered = sorted(merged.values(), key=lambda candle: candle.open_time)
        candles = ordered[:count] if request.count_direction == "forward" else ordered[-count:]
        return CandleResult(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start=result_start,
            end=result_end,
            candles=candles,
            price_display_decimals=symbol.price_display_decimals,
        )

    async def _load_page(
        self,
        page: CountScanPage,
        request: CandleRequest,
        symbol: SupportedSymbol,
        timeframe: Timeframe,
        policy: MarketSessionPolicy,
        current: Candle | None,
        now: datetime,
    ) -> tuple[dict[datetime, Candle], int, int, int, float, float]:
        expected_set = set(page.expected_opens)
        database_started = time.perf_counter()
        try:
            persisted = await self._repository.list_complete(
                symbol,
                request.timeframe,
                page.start,
                page.end,
            )
        except BaseException as exc:
            _set_stage_elapsed(exc, "database", time.perf_counter() - database_started)
            raise
        database_ms = (time.perf_counter() - database_started) * 1000
        persisted = [
            candle
            for candle in persisted
            if candle.open_time in expected_set
            and policy.is_eligible(candle.open_time, request.timeframe)
        ]
        persisted_opens = {candle.open_time for candle in persisted}
        cached_opens = (
            {current.open_time}
            if current is not None
            and current.open_time in expected_set
            and policy.is_eligible(current.open_time, request.timeframe)
            else set()
        )

        normalized: list[Candle] = []
        provider_call_count = 0
        provider_rows = 0
        provider_ms = 0.0
        if len(persisted_opens | cached_opens) < len(expected_set):
            provider_call_count = 1
            provider_started = time.perf_counter()
            try:
                fetched = await self._provider.fetch_candles(
                    symbol=symbol,
                    timeframe=request.timeframe,
                    provider_interval=timeframe.provider_interval,
                    start=page.start,
                    end=page.end,
                    limit=min(len(page.expected_opens) + 1, self._max_candles),
                )
            except BaseException as exc:
                _set_stage_elapsed(exc, "database", database_ms / 1000)
                _set_stage_elapsed(exc, "provider", time.perf_counter() - provider_started)
                raise
            provider_rows = len(fetched)
            normalized = [
                replace(candle, complete=candle.close_time <= now)
                for candle in fetched
                if candle.open_time in expected_set
                and policy.is_eligible(candle.open_time, request.timeframe)
            ]
            provider_ms = (time.perf_counter() - provider_started) * 1000
            await self._store_normalized(normalized, now)

        page_merged = {candle.open_time: candle for candle in normalized}
        page_merged.update({candle.open_time: candle for candle in persisted})
        if current is not None and current.open_time in expected_set:
            page_merged.setdefault(current.open_time, current)
        return (
            page_merged,
            provider_call_count,
            len(persisted),
            provider_rows,
            database_ms,
            provider_ms,
        )

    async def _store_normalized(self, candles: list[Candle], now: datetime) -> None:
        await self._repository.upsert_complete([candle for candle in candles if candle.complete])
        if self._cache is not None:
            for candle in candles:
                if not candle.complete:
                    await self._cache.put(candle, stored_at=now)


def _set_stage_elapsed(exc: BaseException, stage: str, elapsed_seconds: float) -> None:
    setattr(exc, f"_count_{stage}_elapsed_ms", elapsed_seconds * 1000)


def _stage_elapsed(exc: BaseException, stage: str) -> float:
    value = getattr(exc, f"_count_{stage}_elapsed_ms", 0.0)
    return value if isinstance(value, (int, float)) else 0.0
