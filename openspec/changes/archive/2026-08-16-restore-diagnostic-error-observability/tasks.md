## 1. Logging and correlation foundation

- [x] 1.1 Add configurable `LOG_LEVEL` with an `INFO` default and configure standard-library JSON logging to `stdout` with a safe fallback stream.
- [x] 1.2 Add request-scoped diagnostic context for bounded `request_id`, `job_id`, and common market-data fields.
- [x] 1.3 Add HTTP request correlation middleware and response-header propagation; apply the same context at WebSocket handshakes and standalone background executions.
- [x] 1.4 Add stable event naming, safe-field construction, secret redaction, latency capture, and the agreed severity policy.
- [x] 1.5 Add the high-volume warning limiter with a 60-second event-key window and `suppressed_count`.

## 2. Domain failure diagnostics

- [x] 2.1 Extend provider and database domain failures with safe operation context, `failure_reason`, `retryable`, and exception chaining.
- [x] 2.2 Implement the agreed failure taxonomy and conservative unknown-failure mapping without adding automatic retry.
- [x] 2.3 Update specialized and global exception handlers so boundary owners log full tracebacks once while API responses remain sanitized and stable.
- [x] 2.4 Add the global unexpected-error handler returning `500 INTERNAL_ERROR` with the correlation response header.

## 3. Provider and persistence instrumentation

- [x] 3.1 Instrument YFINANCE REST and stream failures, including safe DataFrame shape/columns and failed-row timestamp/reason metadata without raw payloads.
- [x] 3.2 Instrument TWELVE_DATA and BINANCE_SPOT REST/stream failures with provider status/code, operation, symbol, latency, and safe classification.
- [x] 3.3 Instrument database session and repository query/write failures without logging SQL credentials, DSNs, or raw records.
- [x] 3.4 Instrument quote/candle routing and cache fallback so unexpected empty responses and `CACHE_FALLBACK_AFTER_PROVIDER_FAILURE` are visible without changing fallback behavior.
- [x] 3.5 Instrument WebSocket lifecycle, reconnect, persistence, queue-drop, and rejected-event paths using the agreed severity and rate limiting.
- [x] 3.6 Instrument crawl, economic-calendar, cron, and backfill failures with safe context and `job_id` where no HTTP request exists.

## 4. Readiness and health contracts

- [x] 4.1 Add `GET /ready` with sanitized `READY`/`NOT_READY` responses, UTC time, required configuration checks, and a PostgreSQL connectivity probe.
- [x] 4.2 Ensure `/ready` never calls market-data providers and logs missing/unavailable dependencies without exposing secrets.
- [x] 4.3 Preserve `/health` as an upstream-independent liveness endpoint and update its tests for dependency-unavailable conditions.

## 5. Verification

- [x] 5.1 Add unit tests for request/job correlation, JSON fields, redaction, failure taxonomy, retryability, traceback ownership, severity, and rate limiting.
- [x] 5.2 Add API and WebSocket tests for `X-Request-ID`, sanitized provider/database errors, generic `INTERNAL_ERROR`, and unchanged client-error contracts.
- [x] 5.3 Add provider tests for YFINANCE, TWELVE_DATA, and BINANCE_SPOT diagnostics, including empty response and malformed normalization cases.
- [x] 5.4 Add database, cache fallback, stream, crawl, economic-calendar, cron, and backfill diagnostic tests using existing fake/repository seams.
- [x] 5.5 Add readiness tests for successful dependency checks, missing configuration, database failure, no-provider-call behavior, and unchanged liveness.

## 6. Documentation and validation

- [x] 6.1 Update the API, system-design, tech-stack, deployment, and domain glossary documentation for structured diagnostics, correlation headers, `job_id`, and `/ready`.
- [x] 6.2 Verify that no new runtime dependency or database migration is introduced and that existing Provider Selection/cross-provider fallback rules remain unchanged.
- [x] 6.3 Run the focused tests, full test suite, lint/type checks, and OpenSpec validation; resolve any contract or documentation drift.
