## 1. Core Runner

- [x] 1.1 Add `app/core/cronjob.py` with `Cronjob`, `CronjobStatus`, and `CronjobManager`.
- [x] 1.2 Implement registration with duplicate-name validation and support for registering after manager start.
- [x] 1.3 Implement start/stop lifecycle with one task per enabled job and clean cancellation.
- [x] 1.4 Implement scheduled runs with `run_on_start`, interval sleeps, and no overlapping runs.
- [x] 1.5 Implement on-demand `run_once(name)` using the same execution guard.
- [x] 1.6 Implement status tracking for success, failure, running state, counters, timestamps, and last error.

## 2. Application Wiring

- [x] 2.1 Create and start a `CronjobManager` from FastAPI lifespan.
- [x] 2.2 Store the manager on `application.state` so feature modules can register jobs.
- [x] 2.3 Stop the manager during lifespan shutdown before disposing shared resources.

## 3. Tests

- [x] 3.1 Add unit tests for registration, duplicate rejection, disabled jobs, and after-start registration.
- [x] 3.2 Add unit tests for run-on-start, interval execution, on-demand execution, and unknown job errors.
- [x] 3.3 Add unit tests for non-overlapping scheduled and on-demand runs.
- [x] 3.4 Add unit tests for failure isolation, status updates, and clean shutdown.
- [x] 3.5 Update lifespan tests to verify the cronjob manager starts idle and stops cleanly.

## 4. Validation

- [x] 4.1 Run `uv run pytest tests/unit/test_cronjob.py tests/unit/test_stream_lifespan.py`.
- [x] 4.2 Run `uv run ruff check app tests`.
- [x] 4.3 Run `uv run mypy app`.
