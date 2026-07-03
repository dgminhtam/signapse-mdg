## Context

The gateway already has in-process background loops inside stream-specific services, but there is no shared lifecycle helper for periodic feature jobs. Economic-calendar refresh is the first expected caller: it needs interval execution, optional on-start refresh, manual refresh, status, and clean shutdown from FastAPI lifespan.

This core is deliberately not a durable scheduler. It runs only while the gateway process is alive and does not coordinate across multiple Uvicorn workers or replicas.

## Goals / Non-Goals

**Goals:**
- Add `app/core/cronjob.py` with a reusable async interval runner.
- Use only `asyncio`, `dataclasses`, `datetime`, and `logging`.
- Support job registration before or after manager start.
- Track minimal runtime status for operators and tests.
- Keep failure handling isolated per job.
- Shut down task loops without unhandled task exceptions.

**Non-Goals:**
- No cron expressions, OS cron, Celery, APScheduler, retry queue, DB job table, or distributed lock.
- No persistent job history.
- No admin HTTP API in this change.
- No economic-calendar implementation in this change.

## Decisions

### Use an in-process manager

`CronjobManager` will own one `asyncio.Task` loop per enabled job. FastAPI lifespan can create the manager, register feature jobs, call `start()` before yielding, and call `stop()` during shutdown.

Alternative considered: keep feature-specific loops. Rejected because lifecycle, cancellation, status, and failure handling would be copied into every background feature.

Alternative considered: Celery/APScheduler. Rejected because the current need is simple interval work in the gateway process and the repo does not need a new runtime dependency yet.

### Keep the job contract tiny

`Cronjob` exposes `name`, `interval_seconds`, `run_on_start`, `enabled`, and async `run_once()`. Feature-specific settings stay outside the core and are passed into concrete jobs.

Alternative considered: add cron expressions, retries, jitter, time windows, and job metadata now. Rejected until there is a measured operational need.

### Prevent overlapping runs per job

The manager will keep per-job runtime state. If a scheduled tick fires while the same job is still running, that tick is skipped and the existing run continues. On-demand `run_once(name)` uses the same guard.

Alternative considered: queue missed ticks. Rejected because interval jobs such as economic-calendar refresh only need the latest refresh, not backlog replay.

### Isolate failures and update status

Each job execution is wrapped by the manager. Exceptions are logged, failure counters and timestamps are updated, and other job loops continue.

Alternative considered: let exceptions crash the task. Rejected because one bad feature job should not silently stop all periodic work.

### Use snake_case status fields internally

`CronjobStatus` will be a Python dataclass with `name`, `enabled`, `running`, `last_started_at`, `last_finished_at`, `last_succeeded_at`, `last_failed_at`, `last_error`, `run_count`, and `failure_count`. If status is later exposed through an HTTP API, that API can map fields to camelCase at the DTO boundary.

Alternative considered: camelCase fields in core. Rejected because repo Python code uses snake_case.

## Risks / Trade-offs

- Multiple workers can run the same cronjob more than once -> document per-process semantics; add a distributed lock only when deployment needs exactly-once behavior.
- Long-running jobs can delay shutdown while being cancelled -> cancel tasks and await them with `return_exceptions=True`.
- In-memory status is lost on process restart -> acceptable for V1; add persistence only when operations require historical runs.
- A job can fail repeatedly every interval -> log each failure and expose `failure_count`; add backoff only if repeated failures become noisy or costly.
