import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.core.cronjob import Cronjob, CronjobManager


class CountingJob(Cronjob):
    def __init__(
        self,
        name: str = "job",
        *,
        interval_seconds: float = 10,
        run_on_start: bool = False,
        enabled: bool = True,
        block: bool = False,
    ) -> None:
        super().__init__(name, interval_seconds, run_on_start, enabled)
        self.calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.block = block

    async def run_once(self) -> None:
        self.calls += 1
        self.started.set()
        if self.block:
            await self.release.wait()


class FailingJob(Cronjob):
    def __init__(self, name: str = "failing") -> None:
        super().__init__(name, interval_seconds=10, run_on_start=True)

    async def run_once(self) -> None:
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_register_rejects_duplicates() -> None:
    manager = CronjobManager()
    manager.register(CountingJob("sync"))

    with pytest.raises(ValueError):
        manager.register(CountingJob("sync"))

    assert manager.status()[0].name == "sync"


@pytest.mark.asyncio
async def test_disabled_job_does_not_start() -> None:
    manager = CronjobManager()
    job = CountingJob(enabled=False, interval_seconds=0.01)
    manager.register(job)

    await manager.start()
    await asyncio.sleep(0.03)
    await manager.stop()

    assert job.calls == 0
    assert manager.status()[0].enabled is False


@pytest.mark.asyncio
async def test_register_after_start_begins_enabled_job_loop() -> None:
    manager = CronjobManager()
    await manager.start()

    job = CountingJob(interval_seconds=0.01)
    manager.register(job)
    await asyncio.wait_for(job.started.wait(), timeout=1)
    await manager.stop()

    assert job.calls >= 1


@pytest.mark.asyncio
async def test_run_on_start_and_interval_execution() -> None:
    manager = CronjobManager()
    job = CountingJob(interval_seconds=0.01, run_on_start=True)
    manager.register(job)

    await manager.start()
    await asyncio.wait_for(job.started.wait(), timeout=1)
    await asyncio.sleep(0.02)
    await manager.stop()

    assert job.calls >= 2


@pytest.mark.asyncio
async def test_run_once_executes_job_and_unknown_name_fails() -> None:
    manager = CronjobManager()
    job = CountingJob()
    manager.register(job)

    await manager.run_once("job")

    assert job.calls == 1
    with pytest.raises(KeyError):
        await manager.run_once("missing")


@pytest.mark.asyncio
async def test_on_demand_run_skips_while_same_job_is_running() -> None:
    manager = CronjobManager()
    job = CountingJob(block=True)
    manager.register(job)

    first = asyncio.create_task(manager.run_once("job"))
    await asyncio.wait_for(job.started.wait(), timeout=1)
    await manager.run_once("job")
    job.release.set()
    await asyncio.wait_for(first, timeout=1)

    assert job.calls == 1


@pytest.mark.asyncio
async def test_scheduled_run_skips_while_same_job_is_running() -> None:
    manager = CronjobManager()
    job = CountingJob(interval_seconds=0.01, block=True)
    manager.register(job)

    first = asyncio.create_task(manager.run_once("job"))
    await asyncio.wait_for(job.started.wait(), timeout=1)
    await manager.start()
    await asyncio.sleep(0.03)
    await manager.stop()
    job.release.set()
    await asyncio.wait_for(first, timeout=1)

    assert job.calls == 1


@pytest.mark.asyncio
async def test_failure_updates_status_and_does_not_stop_other_jobs() -> None:
    manager = CronjobManager(
        clock=_Clock(datetime(2026, 6, 30, tzinfo=UTC)),
    )
    failing = FailingJob()
    healthy = CountingJob("healthy", run_on_start=True)
    manager.register(failing)
    manager.register(healthy)

    await manager.start()
    await asyncio.wait_for(healthy.started.wait(), timeout=1)
    await asyncio.sleep(0)
    await manager.stop()

    statuses = {status.name: status for status in manager.status()}
    assert statuses["failing"].run_count == 1
    assert statuses["failing"].failure_count == 1
    assert statuses["failing"].last_error == "boom"
    assert statuses["failing"].last_failed_at is not None
    assert statuses["healthy"].run_count == 1
    assert statuses["healthy"].failure_count == 0


@pytest.mark.asyncio
async def test_stop_cancels_running_job_cleanly() -> None:
    manager = CronjobManager()
    job = CountingJob(run_on_start=True, block=True)
    manager.register(job)

    await manager.start()
    await asyncio.wait_for(job.started.wait(), timeout=1)
    await asyncio.wait_for(manager.stop(), timeout=1)

    status = manager.status()[0]
    assert status.running is False
    assert status.run_count == 0


class _Clock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        self.value += timedelta(seconds=1)
        return self.value
