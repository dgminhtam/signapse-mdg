## Why

The gateway needs a small reusable way to run periodic background work inside the FastAPI process, starting with economic-calendar refreshes. Existing background loops are feature-specific, and adding another one directly would duplicate lifecycle, status, cancellation, and failure-isolation rules.

## What Changes

- Add an in-process async cronjob core for interval-based background jobs.
- Provide a `Cronjob` base contract with `name`, `interval_seconds`, `run_on_start`, `enabled`, and `run_once()`.
- Provide a `CronjobManager` that registers jobs, starts/stops loops from FastAPI lifespan, runs jobs on demand, and exposes status.
- Ensure each job has one loop, does not overlap runs, isolates failures, and shuts down cleanly.
- Keep this as a per-process runner only; it will not provide OS cron, Celery, persistent job state, distributed locks, or exactly-once execution across workers.

## Capabilities

### New Capabilities
- `cronjob-core`: Reusable in-process async cronjob runner for FastAPI background jobs.

### Modified Capabilities
- None.

## Impact

- Affected code: new `app/core/cronjob.py`, FastAPI lifespan wiring when jobs are registered, and focused unit tests.
- Affected systems: in-process gateway lifecycle only.
- Public APIs: none.
- Dependencies and migrations: none.
