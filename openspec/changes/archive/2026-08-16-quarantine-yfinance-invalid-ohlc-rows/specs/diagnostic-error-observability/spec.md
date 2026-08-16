## ADDED Requirements

### Requirement: Partial YFINANCE row quarantine is observable

The gateway SHALL emit one aggregate structured `WARNING` diagnostic event when
YFINANCE normalization excludes one or more isolated OHLC-bounds-invalid rows while
returning other valid candles. The event SHALL retain
`failure_reason=INVALID_PAYLOAD` and `retryable=false`, identify the quarantine action
and partial result, and include safe bounded row timestamps, OHLC scalar values, row
reasons, and the skipped-row count. It SHALL NOT include a raw DataFrame, complete raw
provider response, credentials, DSN, or unrestricted exception text.

#### Scenario: Mixed valid and invalid rows emit one aggregate warning

- **WHEN** a YFINANCE fetch contains at least one valid row and one row that violates
  the OHLC bounds predicate
- **THEN** the provider boundary emits one `WARNING` diagnostic event for that fetch
- **AND** the event includes provider/request context, `INVALID_PAYLOAD`,
  `retryable=false`, partial/quarantine action metadata, the skipped count, and safe
  bounded details for the affected rows
- **AND** the public candle response remains sanitized and contains only valid candles

#### Scenario: Repeated equivalent quarantine warnings are rate-limited

- **WHEN** equivalent quarantines for the same provider, provider symbol, timeframe,
  failed row timestamp, and reason occur repeatedly within 60 seconds
- **THEN** the first warning is emitted
- **AND** subsequent equivalent warnings are suppressed
- **AND** the next emitted warning includes `suppressed_count`

#### Scenario: No partial warning is emitted for batch-fatal payload failure

- **WHEN** a YFINANCE payload has a structural or numeric error that makes the batch
  invalid, or all non-empty rows are quarantined
- **THEN** the existing provider-failure diagnostic boundary records the batch failure
- **AND** the gateway does not report the result as a successful partial fill

#### Scenario: Migration logging does not disable gateway diagnostics

- **WHEN** Alembic configures logging for a migration in a process that also hosts or
  invokes gateway code
- **THEN** existing application and provider loggers remain enabled
- **AND** subsequent YFINANCE quarantine diagnostics remain observable
