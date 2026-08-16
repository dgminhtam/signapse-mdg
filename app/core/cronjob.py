import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.core.observability import (
    bind_context,
    failure_metadata,
    log_event,
    log_failure,
    reset_context,
)
from app.domain.errors import DatabaseUnavailableError, ProviderUnavailableError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Cronjob:
    name: str
    interval_seconds: float
    run_on_start: bool = False
    enabled: bool = True

    async def run_once(self) -> None:
        raise NotImplementedError


@dataclass(slots=True)
class CronjobStatus:
    name: str
    enabled: bool
    running: bool = False
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_succeeded_at: datetime | None = None
    last_failed_at: datetime | None = None
    last_error: str | None = None
    run_count: int = 0
    failure_count: int = 0


@dataclass(slots=True)
class _CronjobState:
    job: Cronjob
    status: CronjobStatus
    task: asyncio.Task[None] | None = None


class CronjobManager:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._jobs: dict[str, _CronjobState] = {}
        self._lock = asyncio.Lock()
        self._started = False
        self._stopping = False

    def register(self, job: Cronjob) -> None:
        if job.name in self._jobs:
            raise ValueError(f"Cronjob already registered: {job.name}")
        state = _CronjobState(
            job=job,
            status=CronjobStatus(name=job.name, enabled=job.enabled),
        )
        self._jobs[job.name] = state
        if self._started and not self._stopping and job.enabled:
            state.task = self._create_loop_task(job.name)

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._stopping = False
        for name, state in self._jobs.items():
            if state.job.enabled:
                state.task = self._create_loop_task(name)

    async def stop(self) -> None:
        if not self._started or self._stopping:
            return
        self._stopping = True
        tasks = [state.task for state in self._jobs.values() if state.task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for state in self._jobs.values():
            state.task = None
        self._started = False
        self._stopping = False

    async def run_once(self, name: str) -> None:
        state = self._jobs.get(name)
        if state is None:
            raise KeyError(name)
        if not state.job.enabled:
            return
        await self._run_once(state)

    def status(self) -> list[CronjobStatus]:
        return [
            CronjobStatus(
                name=state.status.name,
                enabled=state.status.enabled,
                running=state.status.running,
                last_started_at=state.status.last_started_at,
                last_finished_at=state.status.last_finished_at,
                last_succeeded_at=state.status.last_succeeded_at,
                last_failed_at=state.status.last_failed_at,
                last_error=state.status.last_error,
                run_count=state.status.run_count,
                failure_count=state.status.failure_count,
            )
            for state in self._jobs.values()
        ]

    def _create_loop_task(self, name: str) -> asyncio.Task[None]:
        return asyncio.create_task(self._loop(name), name=f"cronjob-{name}")

    async def _loop(self, name: str) -> None:
        state = self._jobs[name]
        try:
            if state.job.run_on_start:
                await self._run_once(state)
            while True:
                await asyncio.sleep(state.job.interval_seconds)
                await self._run_once(state)
        except asyncio.CancelledError:
            log_event(
                logger,
                logging.INFO,
                "cronjob_cancelled",
                operation="cronjob",
                job_id=uuid4().hex,
            )
            raise

    async def _run_once(self, state: _CronjobState) -> None:
        async with self._lock:
            if state.status.running:
                return
            state.status.running = True
            state.status.last_started_at = self._clock()
        job_id = uuid4().hex
        token = bind_context(job_id=job_id)
        try:
            await state.job.run_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            now = self._clock()
            async with self._lock:
                state.status.last_finished_at = now
                state.status.last_failed_at = now
                state.status.last_error = str(exc)
                state.status.run_count += 1
                state.status.failure_count += 1
            if isinstance(exc, (DatabaseUnavailableError, ProviderUnavailableError)):
                metadata = failure_metadata(exc)
                log_event(
                    logger,
                    logging.ERROR,
                    "cronjob_failed",
                    operation="cronjob",
                    job_id=job_id,
                    **metadata,
                )
            else:
                log_failure(
                    logger,
                    "cronjob_failed",
                    exc,
                    operation="cronjob",
                    job_id=job_id,
                )
        else:
            now = self._clock()
            async with self._lock:
                state.status.last_finished_at = now
                state.status.last_succeeded_at = now
                state.status.last_error = None
                state.status.run_count += 1
        finally:
            async with self._lock:
                state.status.running = False
            reset_context(token)


__all__ = ["Cronjob", "CronjobManager", "CronjobStatus"]
