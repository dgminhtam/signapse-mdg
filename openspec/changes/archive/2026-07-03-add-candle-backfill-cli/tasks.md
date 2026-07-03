## 1. CLI Scope and Wiring

- [x] 1.1 Add `app/backfill_candles.py` with an async `main` runnable via `python -m app.backfill_candles`.
- [x] 1.2 Parse `--from`, `--to`, `--timeframes`, and optional `--symbols`, `--providers`, and `--asset-classes` filters with `argparse`.
- [x] 1.3 Build settings, SQLAlchemy session factory, `PostgresCandleRepository`, enabled symbol lookup, candle provider router, and `CandleService` using existing project code.

## 2. Backfill Behavior

- [x] 2.1 Validate UTC half-open range and supported timeframe inputs before provider access.
- [x] 2.2 Select matching enabled registry symbols and reject unknown or disabled explicit symbols.
- [x] 2.3 Split each symbol/timeframe range into chunks within `MAX_CANDLES_PER_REQUEST`.
- [x] 2.4 Call `CandleService.get_candles()` for each chunk with `cache=None` so existing gap detection and upserts perform the fill.
- [x] 2.5 Report per-chunk progress and sanitized failures, continuing the run and returning non-zero when any chunk fails.

## 3. Verification

- [x] 3.1 Add unit coverage for argument parsing, UTC range validation, symbol filtering, and chunk generation.
- [x] 3.2 Add service-level or integration coverage proving fully persisted chunks skip provider calls and reruns do not create duplicates.
- [x] 3.3 Run `uv run pytest` for the focused backfill and candle tests.
- [x] 3.4 Run `uv run ruff check .` and `uv run mypy app`.

## 4. Documentation

- [x] 4.1 Document the internal backfill command, required environment, and example invocation in the project docs or README.
- [x] 4.2 Note that scheduler, job status persistence, distributed locking, and no-data tombstones are intentionally deferred.
