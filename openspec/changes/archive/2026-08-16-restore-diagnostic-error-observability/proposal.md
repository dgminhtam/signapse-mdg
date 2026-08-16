## Why

Provider failures such as the reported YFINANCE `503 PROVIDER_UNAVAILABLE` currently hide the upstream exception and often lack enough context to diagnose the real cause. Database, fallback, WebSocket, crawl, and background failures have similar observability gaps. This change restores safe internal diagnostics without exposing sensitive details or changing the public error contract.

## What Changes

- Add request-scoped correlation using bounded `X-Request-ID` values for REST and WebSocket operations, plus `job_id` for background work.
- Add JSON structured logging to `stdout` using the standard library, with configurable `LOG_LEVEL` defaulting to `INFO`.
- Enrich provider, database, crawl, stream, fallback, backfill, and unexpected-error paths with safe context, failure taxonomy, retryability, latency, and traceback ownership.
- Preserve sanitized public error responses and existing status/code/body behavior; echo the correlation ID in a response header.
- Add an explicit global `500 INTERNAL_ERROR` boundary for unexpected exceptions.
- Preserve valid empty/no-data and cache-fallback behavior while making unexpected empty responses and fallbacks visible in logs.
- Rate-limit high-volume warning events and include the number of suppressed events.
- Add `/ready` for process/config/database readiness while keeping `/health` as an upstream-independent liveness endpoint.
- Add tests and update the observability and health documentation to match the runtime behavior.

## Capabilities

### New Capabilities

- `diagnostic-error-observability`: Safe request/job correlation, structured diagnostic logging, internal failure taxonomy, retryability classification, traceback ownership, redaction, severity, and rate limiting.
- `service-readiness`: A readiness endpoint that checks required configuration and database connectivity without making live provider calls.

### Modified Capabilities

None. Existing public API error contracts and the `service-health` liveness contract remain unchanged.

## Impact

- Affects the FastAPI request and WebSocket boundaries, exception handlers, domain provider/database errors, all REST market-data provider adapters, stream lifecycle, crawl/economic-calendar paths, cache fallback, and background/backfill execution.
- Adds a response header and a new readiness endpoint; it does not change existing response bodies, status codes, provider selection, cache semantics, or cross-provider fallback rules.
- Adds one configurable logging setting and no new runtime dependency or database migration.
- Requires unit and integration coverage for correlation, structured logs, error sanitization, provider/database diagnostics, fallback visibility, readiness, and high-volume log suppression.
