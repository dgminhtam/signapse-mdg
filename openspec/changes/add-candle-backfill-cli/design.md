## Context

Historical candle requests already read complete candles from PostgreSQL, calculate missing
eligible slots, fetch only gaps through the provider router, and upsert complete fetched candles.
Backfill should run that same behavior before users request the data, not introduce a second candle
pipeline.

## Goals / Non-Goals

**Goals:**
- Provide an internal CLI entry point for pre-filling `market_data_candles`.
- Reuse `CandleService`, `PostgresCandleRepository`, `CandleProviderRouter`, and provider builders.
- Chunk long ranges so existing candle-count limits and provider limits are respected.
- Keep repeated runs idempotent and cheap by relying on existing gap detection and upserts.

**Non-Goals:**
- No scheduler, job table, distributed lock, or persistent job status.
- No public HTTP endpoint or WebSocket contract change.
- No tombstone/no-data table for provider gaps.
- No new database migration or external dependency.

## Decisions

### Reuse CandleService

The CLI will construct the same repository and provider router used by `/v1/candles`, then call
`CandleService.get_candles()` for each chunk. This keeps market-session filtering, provider
normalization, completion checks, gap detection, and idempotent persistence in one place.

Alternative considered: write a dedicated backfill service. Rejected because it would duplicate
the highest-risk candle rules.

### Start With a CLI Module

Expose backfill as `uv run python -m app.backfill_candles` with `argparse` options for `from`,
`to`, `timeframes`, and optional symbol/provider filters.

Alternative considered: background worker in the FastAPI process. Rejected for now because manual
or cron-driven execution is enough and avoids process-lifecycle complexity.

### Chunk Before Calling the Service

The CLI will split each requested `(symbol, timeframe, range)` into chunks no larger than the
existing `MAX_CANDLES_PER_REQUEST` count. Each chunk is passed to the service independently.

Alternative considered: raise the service limit for backfill. Rejected because provider limits and
existing tests already assume bounded candle requests.

### Fail Fast Per Chunk, Continue by Default

The CLI should log failures with symbol, timeframe, and chunk boundaries. A provider or database
failure for one chunk should not corrupt existing rows; idempotent upsert keeps reruns safe. The
first version can return non-zero if any chunk fails.

Alternative considered: persistent retry queue. Rejected until repeated operational failures prove
it is needed.

## Risks / Trade-offs

- Provider no-data gaps may be retried on every run -> keep logs visible; add no-data tombstones
  only if repeated empty fills become costly.
- Running multiple backfills concurrently can duplicate provider calls -> run one CLI instance
  operationally; add locking only if deployment needs it.
- Provider rate limits can be hit on large ranges -> default to sequential execution; add small
  per-provider concurrency only after measuring.
- The CLI depends on provider credentials for missing ranges -> fully persisted ranges still work,
  but missing third-party data fails like `/v1/candles`.
