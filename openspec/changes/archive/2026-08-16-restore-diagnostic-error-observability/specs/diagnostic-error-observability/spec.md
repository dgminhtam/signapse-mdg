## ADDED Requirements

### Requirement: Request and job correlation

The gateway SHALL assign one bounded, log-safe correlation identifier to every REST request and WebSocket handshake. It SHALL preserve a valid inbound `X-Request-ID`, generate a new UUID when the header is missing or invalid, propagate the identifier through the operation context, and echo it in REST responses. Standalone cron and backfill executions SHALL use a `job_id` instead of fabricating an HTTP request identifier.

#### Scenario: Valid inbound request ID is preserved

- **WHEN** a REST client sends a valid bounded `X-Request-ID`
- **THEN** the gateway uses that value in request, provider, database, and response context
- **AND** the value is returned in the `X-Request-ID` response header

#### Scenario: Missing or unsafe request ID is replaced

- **WHEN** a REST client omits `X-Request-ID` or sends a value that exceeds the allowed length or character set
- **THEN** the gateway generates a new UUID
- **AND** the generated value is used in logs and returned in the response header

#### Scenario: Background execution uses a job ID

- **WHEN** a cron or backfill operation runs without an HTTP request
- **THEN** the gateway assigns a `job_id` for its diagnostic events
- **AND** it does not claim that the execution came from an HTTP `request_id`

### Requirement: Structured diagnostic log output

The gateway SHALL emit JSON structured logs to `stdout` using the standard library logging system. The log level SHALL be configurable through `LOG_LEVEL` and SHALL default to `INFO`. Diagnostic events SHALL use stable `event` names and snake-case fields, including applicable operation, correlation, Provider Identifier, provider symbol, canonical symbol, timeframe, request range, public error code, failure reason, retryability, exception type, upstream status/code, and latency. Fields that are not applicable SHALL be omitted or null without exposing raw upstream payloads.

#### Scenario: Provider failure contains safe diagnostic context

- **WHEN** a configured provider fails while serving a candle request
- **THEN** the gateway emits a JSON diagnostic event containing the operation, Provider Identifier, provider symbol, canonical symbol, timeframe, request range, failure classification, retryability, exception type, and latency when available
- **AND** the event does not contain an API key, DSN, raw provider response, or complete raw DataFrame

#### Scenario: Log level is configurable

- **WHEN** the gateway starts without an explicit `LOG_LEVEL`
- **THEN** the effective application log level is `INFO`
- **AND** an explicit valid `LOG_LEVEL` changes the emitted severity threshold

### Requirement: Internal failure taxonomy and retryability

Provider and database domain failures SHALL carry safe internal metadata using the agreed `failure_reason` taxonomy: `REQUEST_FAILED`, `TIMEOUT`, `RATE_LIMITED`, `AUTH_FAILED`, `EMPTY_RESPONSE`, `INVALID_PAYLOAD`, `PROVIDER_NOT_CONFIGURED`, `DATABASE_QUERY_FAILED`, and `DATABASE_WRITE_FAILED`. The gateway SHALL set `retryable=true` only for known timeout, network/transient, upstream `429`, or upstream `5xx` failures. Known permanent failures and unknown classifications SHALL use `retryable=false`. These fields SHALL remain internal and SHALL not trigger automatic retry.

#### Scenario: Transient upstream failure is classified as retryable

- **WHEN** a provider request times out or returns an upstream `429` or `5xx`
- **THEN** the diagnostic event contains the matching transient failure reason
- **AND** `retryable` is `true`
- **AND** the gateway does not automatically retry the request

#### Scenario: Permanent provider failure is classified as non-retryable

- **WHEN** a provider rejects authentication, is not configured, or returns a malformed payload
- **THEN** the diagnostic event uses the corresponding permanent failure reason
- **AND** `retryable` is `false`

#### Scenario: Unknown failure is classified conservatively

- **WHEN** the gateway cannot confidently map an exception to a more specific failure reason
- **THEN** the diagnostic event uses `REQUEST_FAILED`
- **AND** `retryable` is `false`
- **AND** the original exception type and chained cause remain available to the internal log

### Requirement: Sanitized public error boundary

The gateway SHALL preserve stable public error codes, HTTP statuses, and response bodies for known provider, database, and request failures. It SHALL return only sanitized messages and approved details, while correlating the response with `X-Request-ID`. An unexpected exception SHALL be logged as an internal failure and translated to `500 INTERNAL_ERROR` without internal details.

#### Scenario: Provider failure remains sanitized

- **WHEN** a provider boundary raises an enriched provider-unavailable failure
- **THEN** the API returns `503 PROVIDER_UNAVAILABLE` with the existing sanitized message
- **AND** the response does not contain the exception text, upstream payload, API key, or DSN
- **AND** the response includes `X-Request-ID`

#### Scenario: Unexpected exception returns the generic internal error

- **WHEN** an exception escapes all specialized domain boundaries
- **THEN** the gateway logs the full traceback with safe context
- **AND** the API returns `500 INTERNAL_ERROR` without internal diagnostic details

#### Scenario: Valid request errors keep their public contract

- **WHEN** a client sends an invalid request that produces an existing `400` domain error
- **THEN** the gateway keeps the existing status, error code, message, and approved details
- **AND** it does not convert the error into `INTERNAL_ERROR`

### Requirement: Boundary traceback ownership and severity

The boundary that knows the root cause SHALL record the full traceback and safe context exactly once. Downstream API translation handlers SHALL record only a concise summary and SHALL NOT duplicate the full traceback. The gateway SHALL use `ERROR` for hard provider/database/5xx failures, `WARNING` for fallback, partial, rejected, or dropped work, `INFO` for request completion, provider selection, and reconnect lifecycle, and `DEBUG` for expected no-data or non-impacting normalization details.

#### Scenario: Provider boundary owns the traceback

- **WHEN** a provider adapter catches a concrete upstream exception and raises a domain provider failure
- **THEN** the provider boundary emits the full traceback once
- **AND** the API handler emits at most a summary event for the same failure
- **AND** the public response remains sanitized

#### Scenario: Cache fallback is visible at warning severity

- **WHEN** quote resolution serves cached data after a provider failure
- **THEN** the gateway keeps the existing cached response behavior
- **AND** it emits a `WARNING` event identifying the cache fallback and its correlation context

### Requirement: Empty response and fallback semantics remain explicit

The gateway SHALL preserve valid empty/no-data and natural-gap semantics as successful empty outcomes. An unexpected empty provider result or invalid normalized result SHALL be diagnosable as `EMPTY_RESPONSE` or `INVALID_PAYLOAD`. Cache fallback SHALL remain observable as `CACHE_FALLBACK_AFTER_PROVIDER_FAILURE`, and the gateway SHALL not introduce cross-provider fallback.

#### Scenario: Valid natural no-data result is not treated as an outage

- **WHEN** a provider legitimately returns no candle for a valid natural gap or no-data range
- **THEN** the existing successful empty response behavior is preserved
- **AND** no `PROVIDER_UNAVAILABLE` response is manufactured solely because the result is empty

#### Scenario: Unexpected empty result is diagnosable

- **WHEN** a provider returns an empty result where data was expected and the adapter cannot treat it as a valid no-data outcome
- **THEN** the gateway records `EMPTY_RESPONSE` with safe provider and request context
- **AND** the public response follows the existing provider failure contract

### Requirement: High-volume diagnostic events are rate-limited

The gateway SHALL rate-limit warning events for high-volume queue drops, rejected events, and equivalent repeated operational conditions to at most one event per event key in a 60-second window. The next emitted event after suppressed occurrences SHALL include `suppressed_count`.

#### Scenario: Repeated queue drops are suppressed

- **WHEN** the same provider/symbol operational event repeatedly drops messages within 60 seconds
- **THEN** the first warning is emitted immediately
- **AND** subsequent equivalent warnings are suppressed
- **AND** a later emitted warning reports the number of suppressed events

### Requirement: Diagnostic coverage spans all operational boundaries

The diagnostic contract SHALL be applied consistently to YFINANCE, TWELVE_DATA, and BINANCE_SPOT REST/stream paths, database session and repository operations, WebSocket lifecycle, crawl and economic-calendar operations, cache fallback, cron jobs, and backfill jobs.

#### Scenario: Database operation failure is diagnosable

- **WHEN** a repository query or write fails
- **THEN** the gateway records the operation, `DATABASE_QUERY_FAILED` or `DATABASE_WRITE_FAILED`, correlation context, exception type, and traceback at the database boundary
- **AND** the public API retains `503 DATABASE_UNAVAILABLE`

#### Scenario: Background failure is diagnosable

- **WHEN** a cron or backfill operation fails
- **THEN** the gateway emits a structured event containing the `job_id`, operation, failure classification, and traceback
- **AND** it does not rely on truncated exception text or console-only class names

### Requirement: Logging failure does not prevent startup

The gateway SHALL continue starting with a standard error-stream fallback if the structured logging configuration cannot be initialized. Logging setup failure SHALL be observable but SHALL not prevent the application from serving requests.

#### Scenario: Structured logging setup fails

- **WHEN** JSON logging initialization raises a configuration error during startup
- **THEN** the gateway reports the setup failure through the fallback error stream
- **AND** the application remains startable with standard logging
