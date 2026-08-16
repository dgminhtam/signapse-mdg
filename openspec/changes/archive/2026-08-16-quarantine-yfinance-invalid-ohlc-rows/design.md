## Context

The YFINANCE candle adapter currently validates every normalized row strictly and
raises on the first OHLC envelope violation. A real `EURUSD=X` daily payload contains
valid rows alongside a row whose `Low` is greater than `Close`, so one provider row
causes the entire candle request to return `503`.

The existing candle service already preserves provider gaps, persists only complete
valid candles, and does not synthesize missing slots. The existing observability layer
also provides structured events and a 60-second warning limiter. The design should use
those seams rather than add a new service, persistence model, or provider fallback. The
Alembic environment currently uses `fileConfig` defaults that disable application
loggers in a shared process, which can hide the warning this change is intended to
restore.

## Goals / Non-Goals

**Goals:**

- Preserve strict validation for structural and numeric payload corruption.
- Quarantine only an isolated OHLC envelope violation when other rows are valid.
- Return valid candles as a partial result while leaving the invalid timestamp absent.
- Persist/cache valid rows through the existing candle flow.
- Emit safe, aggregate, rate-limited diagnostics for quarantined rows.
- Keep the public response shape, provider selection, and database schema unchanged.

**Non-Goals:**

- Repairing, clamping, rounding, or otherwise altering provider OHLC values.
- Retrying the same malformed payload or falling back to Twelve Data.
- Adding persistent quarantine markers or a new database table.
- Changing the official provider seed or the manually selected runtime mapping.
- Introducing a new public partial-response field or HTTP status.

## Decisions

### Classify only the OHLC envelope failure as row-level quarantine

The normalizer will treat `High < max(Open, Close)` or `Low > min(Open, Close)`
as a row-level data-quality failure. It will collect the row as quarantined and
continue only when other rows can be normalized. Invalid timestamps, duplicate
timestamps, missing fields, malformed/non-finite values, and negative volume remain
batch-fatal because they indicate structural or broadly unsafe payload corruption.

### Use partial success with a natural gap

When at least one valid row remains, the adapter returns only valid normalized candles.
The candle service's existing gap calculation and persistence flow then expose and
persist those rows without creating a replacement for the quarantined timestamp. If
all non-empty rows are quarantined, the adapter raises the existing provider-unavailable
boundary with `INVALID_PAYLOAD`.

### Keep empty payload semantics separate

An empty provider payload remains the existing successful empty result. It is not
treated as an invalid row batch, so no `503` is manufactured solely because a valid
range has no provider rows.

### Reuse existing diagnostics and rate limiting

The adapter will emit one aggregate `WARNING` for a partially normalized fetch through
the existing rate-limited warning helper. The event will retain `INVALID_PAYLOAD` and
`retryable=false`, identify the quarantine action and partial result, and include a
bounded set of safe row timestamps, OHLC scalar values, reasons, and a skipped count.
The safe diagnostic allowlist will be extended only for these bounded scalar/action
fields. The warning key will include provider, provider symbol, timeframe, failed row
timestamp, and reason, using the existing 60-second suppression behavior.

### Preserve application loggers during migration logging setup

Alembic will configure its INI logging with `disable_existing_loggers=False`. This keeps
gateway/provider loggers enabled when migrations run in the same process and does not
change the migration schema or provider selection behavior.

### Keep provider selection and persistence identity unchanged

No mapping, seed, migration, or provider-router behavior changes. A manually active
YFINANCE mapping remains active for testing, while the official Twelve Data seed is
untouched. Valid candles keep their existing provider identity and are persisted/cache
merged by the existing candle service.

### Test at the provider and public-flow seams

Deterministic DataFrame fixtures will exercise row classification at the YFINANCE
normalizer seam. Candle service/API integration coverage will verify the observable
partial response, gap preservation, and persistence behavior. No live Yahoo request is
needed in CI.

## Risks / Trade-offs

- **[Risk]** A `200` response with fewer candles may surprise clients that assumed every
  eligible slot is present. → Preserve the existing natural-gap contract and add an
  explicit regression test for the missing timestamp.
- **[Risk]** The same bad timestamp may be fetched again because no quarantine marker is
  persisted. → Persist valid rows, rate-limit repeated warnings, and defer a durable
  negative-cache/quarantine model until request volume justifies the schema cost.
- **[Risk]** A broad row-level policy could affect other YFINANCE assets. → Apply only
  to the exact OHLC envelope predicate, keep all other validation batch-fatal, and test
  the generic adapter behavior with the EUR/USD incident fixture.
- **[Risk]** Additional diagnostic fields could leak provider payload data. → Allow only
  bounded normalized scalar fields; continue excluding raw DataFrames, credentials,
  unrestricted exception text, and complete provider responses.

## Migration Plan

No database migration or provider mapping change is required. Deploy the adapter,
diagnostic allowlist, tests, and specification changes together. Validate the known
EUR/USD request in a test/staging environment and confirm a `200` response with the
affected timestamp absent and a rate-limited warning emitted. Rollback is code-only:
restore the previous strict normalization behavior; any valid candles already persisted
remain valid and the formerly failing row remains absent.

## Open Questions

None. The provider mapping, partial-result, validation, logging, retry, fallback, and
persistence decisions were confirmed during the requirements review.
