## Why

YFINANCE can return a historical candle batch containing one row whose `Low`/`High`
envelope is inconsistent with its `Open` or `Close`. The current strict normalizer
rejects the entire batch, so a request with otherwise valid candles returns `503`
and loses usable data. The gateway needs to preserve data integrity while allowing
valid rows to be served as a partial result with an observable natural gap.

## What Changes

- Classify an isolated YFINANCE OHLC-bounds violation as a quarantined provider row.
- Return and persist/cache valid rows from a partially usable batch; leave quarantined
  timestamps absent rather than repairing or synthesizing candles.
- Keep structural and numeric payload errors batch-fatal, including invalid timestamps,
  duplicate timestamps, missing OHLC fields, non-finite values, and negative volume.
- Keep empty provider payloads as successful empty results.
- Return `503 PROVIDER_UNAVAILABLE` with internal `INVALID_PAYLOAD` diagnostics when a
  non-empty batch has no valid rows or has only batch-fatal errors.
- Emit one aggregate, rate-limited warning for quarantined rows with safe row-level
  diagnostics while preserving the existing sanitized public API response.
- Keep application loggers enabled when Alembic configures migration logging so provider
  diagnostics are not silently disabled in a shared process.
- **BREAKING**: a batch containing both valid rows and isolated OHLC-bounds-invalid
  rows changes from a provider `503` to a successful partial candle response.
- Keep provider selection, the official Twelve Data seed, manual YFINANCE overrides,
  provider fallback policy, and database schema unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `historical-candles`: Define partial YFINANCE fills, quarantined OHLC-bounds-invalid
  rows, all-invalid batch behavior, and unchanged natural-gap semantics.
- `provider-sdk-integration`: Define row-level YFINANCE quarantine versus batch-fatal
  payload validation while retaining repository-owned normalization.
- `diagnostic-error-observability`: Define aggregate warning fields, partial action
  metadata, safe OHLC diagnostics, and rate limiting for repeated quarantines.

## Impact

- YFINANCE candle normalization and its existing structured logging boundary.
- Safe diagnostic field allowlisting and the existing warning-rate limiter.
- Alembic logging configuration used by migration/test processes.
- YFINANCE provider, candle-service/API, observability, and integration test coverage.
- OpenSpec requirements for historical candles, provider normalization, and diagnostics.
- No provider mapping migration, public response-shape change, new dependency, or
  persistent quarantine storage.
