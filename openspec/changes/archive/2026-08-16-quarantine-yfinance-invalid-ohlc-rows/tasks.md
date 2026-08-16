## 1. Normalize YFINANCE rows

- [x] 1.1 Update YFINANCE history normalization so only an isolated OHLC-envelope violation is quarantinable; keep timestamp, duplicate, required-field, numeric, finite-value, and negative-volume errors batch-fatal.
- [x] 1.2 Return valid normalized candles for mixed payloads, raise `INVALID_PAYLOAD` when a non-empty payload has no valid row, and preserve empty-payload success behavior without repairing, retrying, or falling back.

## 2. Emit safe diagnostics

- [x] 2.1 Extend the existing observability allowlist with the minimum safe fields needed to describe a quarantined row: action, partial status, skipped count, timestamp, reason, and bounded OHLC values.
- [x] 2.2 Emit one aggregate rate-limited WARNING per affected provider fetch using the existing `INVALID_PAYLOAD` and `retryable=false` taxonomy, with suppression metadata while keeping the public response sanitized.
- [x] 2.3 Preserve existing application/provider loggers when Alembic configures migration logging so diagnostics are not disabled in a shared process.

## 3. Verify provider and candle flow

- [x] 3.1 Add provider normalization tests for the EUR/USD regression row and a mixed payload, asserting the invalid row is omitted and valid values are returned unchanged.
- [x] 3.2 Add tests for all-rows-invalid, mixed structural invalidity, empty payloads, no retry, and no cross-provider fallback.
- [x] 3.3 Add service/API coverage asserting partial success keeps the natural gap, persists and merges valid rows normally, and leaves the public response shape unchanged.
- [x] 3.4 Add observability coverage for aggregate fields, WARNING severity, 60-second suppression, `suppressed_count`, and exclusion of raw provider payloads and secrets.

## 4. Run focused verification

- [x] 4.1 Run the focused provider, candle-service/API, and observability tests, then run the full test suite plus applicable lint and type checks.
- [x] 4.2 Revalidate the OpenSpec change strictly and verify that provider mappings, seed data, database schema, public API models, and fallback behavior were not changed.
