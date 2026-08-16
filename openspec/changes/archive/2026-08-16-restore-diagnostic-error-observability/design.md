## Context

The gateway already has stable public error codes and several local logging calls, but the error path is fragmented. Provider adapters and repositories often convert the original exception into a generic domain exception without recording the operation context, while API handlers intentionally return sanitized messages without logging the underlying cause. The current runtime also has no request correlation middleware, no global unexpected-error boundary, and no readiness endpoint.

The change crosses the HTTP, WebSocket, provider, database, crawl, cache, and background-job boundaries. It must preserve the accepted Provider Selection and Provider Mapping behavior: a request remains tied to its selected mapping, and no automatic cross-provider fallback is introduced.

## Goals / Non-Goals

**Goals:**

- Make the real cause of provider, database, crawl, stream, fallback, and background failures diagnosable from safe JSON logs.
- Correlate REST, WebSocket, provider, database, and background work with bounded IDs.
- Keep public errors sanitized and backward-compatible while adding `X-Request-ID`.
- Standardize failure reasons, retryability, severity, traceback ownership, and high-volume suppression.
- Add readiness checking for required configuration and PostgreSQL without making live provider calls.
- Use existing application and test seams with no new runtime dependency or database migration.

**Non-Goals:**

- Automatic retries, backoff, circuit breakers, provider failover, or cross-provider fallback.
- Metrics, distributed tracing, Sentry, log aggregation, file retention, or an audit store.
- Changes to provider support, timeframe limits, cache semantics, Provider Selection, or Historical Price Resolution.
- Adding internal provider-health probes or exposing internal failure details through API bodies.

## Decisions

### 1. Use standard-library JSON logging with request context

The application will configure stdlib logging with a small JSON formatter and `contextvars`-backed request context. Logs will be emitted to `stdout`; `LOG_LEVEL` remains configurable with a default of `INFO`.

The alternative was introducing or completing a structlog-based stack. That would add dependency/configuration work without improving the required diagnostic contract, and the runtime dependency set does not currently provide that stack consistently. Stdlib logging is sufficient for the agreed fields and minimizes rollout risk.

### 2. Correlate at the application boundary

HTTP middleware will validate a bounded inbound `X-Request-ID`, generate a UUID when absent or invalid, place it in request context, and echo it in REST responses. WebSocket handshakes receive the same context treatment. Standalone cron and backfill executions use a generated `job_id` rather than fabricating an HTTP request ID.

This keeps correlation at the highest shared seam and avoids adding provider-specific correlation logic. The ID is not placed in JSON response bodies.

### 3. Preserve a dual-channel error boundary

Provider, database, and crawl boundaries will attach safe metadata to domain exceptions and log the full traceback once, retaining exception chaining. API handlers will log only a concise summary and return the existing stable public code and message. The global unexpected-error handler will log a full traceback because no more specific boundary owns that failure, then return `500 INTERNAL_ERROR`.

Raw provider bodies, DataFrames, API keys, DSNs, and arbitrary exception text are not public response data and are not emitted as unrestricted log fields.

### 4. Use explicit internal failure classification

Domain failures will carry `failure_reason`, `retryable`, `operation`, and available market-data context. Known transient failures are retryable; known permanent/configuration failures are not; unknown failures default to `REQUEST_FAILED` and `retryable=false`.

The classification is diagnostic metadata only. It does not trigger retries or alter current Provider Availability behavior.

### 5. Keep fallback and empty-data semantics unchanged

Valid no-data or natural-gap results remain successful empty outcomes. Unexpected provider emptiness, invalid normalization, and cache fallback become visible log events. A cache fallback continues returning cached data where the existing service already permits it, and no cross-provider fallback is added.

This separates data semantics from diagnostics and preserves the accepted provider-selection ADR.

### 6. Assign traceback ownership and severity by boundary

The boundary where the root cause is known owns the full traceback. Downstream API translation logs only summary context to avoid duplicate stack traces. `ERROR` is used for hard 5xx/provider/database failures, `WARNING` for fallback or partial/rejected work, `INFO` for lifecycle and completion events, and `DEBUG` for expected no-data and normalization detail.

High-volume events such as queue drops and event rejection are keyed and rate-limited to one warning per key per 60 seconds, with `suppressed_count` on the next emitted warning.

### 7. Add readiness as a separate contract

`/health` remains a process liveness endpoint and does not depend on PostgreSQL or providers. `/ready` is a separate unauthenticated endpoint for deployment checks. It validates required configuration and PostgreSQL connectivity, returns a small sanitized status body, and never calls an external market-data provider.

Separating the endpoints avoids making a transient upstream outage flap container liveness while still allowing deployment systems to reject an instance that cannot serve its configured database-backed capabilities.

### 8. Test the highest existing seams

Tests will exercise the HTTP/WebSocket boundary, shared diagnostic context/classification, and existing provider/database/crawl/background boundaries. They will assert observable response and log fields rather than snapshotting every log line or creating one new seam per provider.

## Risks / Trade-offs

- [Risk] JSON logging can still leak data if future callers put raw payloads in `extra` → centralize safe field construction and test redaction with secret-like values.
- [Risk] Request context can be lost in newly created background tasks → create tasks from the existing context-aware lifecycle and use explicit `job_id` for standalone jobs.
- [Risk] Rate limiting can hide the first details of a burst → emit the first warning immediately and report `suppressed_count` when the window permits another event.
- [Risk] Readiness may be `503` in local runs without PostgreSQL → document that `/health` is the local liveness check and `/ready` reflects configured service dependencies.
- [Risk] Standard-library JSON formatting is less feature-rich than a logging platform → keep the event/field contract stable so a collector can be added later without changing callers.

## Migration Plan

1. Add the logging/context primitives and configuration without changing existing response contracts.
2. Add exception context/classification at provider, database, crawl, stream, fallback, and background boundaries.
3. Add request/handshake correlation, public response headers, and the global unexpected-error boundary.
4. Add `/ready`, tests, and documentation updates.
5. Deploy with `LOG_LEVEL=INFO`; use existing runtime stdout collection for retention.

Rollback is application-only: deploy the previous runtime if diagnostic logging or readiness causes operational issues. No database migration or persistent data rollback is required, and existing clients remain compatible because public response bodies and error codes are preserved.

## Open Questions

None. The user has confirmed the error boundary, fields, taxonomy, correlation rules, scope, semantics, logging implementation, readiness behavior, severity, rate limiting, test seams, and rollout constraints.
