## Context

`GET /v1/candles` currently requires both `from` and `to`, requires both timestamps to align to a
duration grid anchored at the Unix epoch, and calculates expected gaps by stepping from `from` in
exact timeframe durations. That works for Binance candles whose open times align to `:00`, but it
does not describe every Twelve Data series. Live validation showed WTI, SPY, and QQQ hourly
candles labeled at `:30`.

The current Twelve Data transport also converts every provider error payload into
`ProviderUnavailableError`. Twelve Data uses an error response with “No data is available on the
specified dates” for a valid range with no rows, so a normal empty result currently becomes HTTP
503.

## Goals / Non-Goals

**Goals:**

- Let clients omit `to` to request candles through the current request time.
- Accept arbitrary explicit UTC instants for `from` and `to`.
- Keep exact half-open range filtering and deterministic response boundaries.
- Preserve provider timestamps without rebucketing or shifting.
- Calculate persistence gaps from symbol/provider-aware expected open times.
- Preserve existing elapsed-range and candle-count safety limits.
- Return an empty candle list when Twelve Data has no data for a valid range.
- Keep existing Binance behavior and persisted identity semantics intact.

**Non-Goals:**

- Do not make `from` optional.
- Do not add relative duration parameters such as `lookback=24h`.
- Do not change supported timeframe values.
- Do not convert provider timestamps into a universal canonical bucket grid.
- Do not synthesize missing candles.
- Do not expose raw Twelve Data error messages or provider error codes publicly.
- Do not redesign market holiday or exceptional closure handling.

## Decisions

### Capture omitted `to` once at the HTTP request boundary

The route passes an injectable UTC clock to request parsing. If the raw `to` value is absent, the
parser captures the clock once and uses that exact instant as the request's exclusive end.

The resolved value is stored in `CandleRequest.end` and returned in the response `to` field. It is
not recalculated later in the service, ensuring validation, provider calls, completion checks, and
response serialization refer to one stable boundary.

An explicitly empty `to=` remains invalid rather than being treated as omitted.

Alternative considered: round `now` up or down to the timeframe. Rounding down excludes valid
provider candles with non-epoch labels, while rounding up creates a future response boundary and
can request unavailable data.

### Remove public timeframe-boundary alignment validation

Both explicit boundaries must remain valid timezone-aware UTC instants, and `from < to` remains
required. The parser no longer calls `is_aligned` for public request boundaries.

The range remains exactly `[from, to)`. A provider candle is eligible when its provider open time
falls within that interval. This makes a request such as `13:00–20:00` naturally include provider
candles at `13:30` through `19:30`.

Alternative considered: require clients to use provider-specific `:30` boundaries. That leaks
provider scheduling into the public contract and becomes unstable if provider mappings change.

### Separate request-size protection from exact schedule enumeration

Before the symbol is loaded, request parsing enforces:

- positive elapsed duration;
- `MAX_CANDLE_RANGE_DAYS`;
- a conservative duration-based upper bound:
  `ceil((to - from) / timeframe duration) <= MAX_CANDLES_PER_REQUEST`.

After the symbol is resolved, the candle service enumerates market/provider-aware expected open
times and can enforce the exact eligible count as a second guard.

Using `ceil` prevents an unaligned partial slot from bypassing the configured count limit.

Alternative considered: defer all count validation until after database symbol resolution. That
would make simple malformed/oversized requests unnecessarily depend on PostgreSQL.

### Introduce a candle schedule boundary

Add a repository-owned `CandleSchedule` abstraction responsible for enumerating expected candle
open times in an exact range. Schedule selection uses the persisted `SupportedSymbol` and
timeframe, alongside the existing market-session policy.

Initial schedules:

- Binance and current epoch-aligned series: duration grid anchored at Unix epoch.
- Twelve Data ETF and WTI intraday series: duration grid anchored to the observed/provider session
  offset, including `:30` for hourly data.
- Daily series: provider date labels, filtered by the existing market-session policy.

The schedule owns expected slot generation only. Provider rows remain authoritative for actual
timestamps and values. Missing expected slots remain gaps and are never synthesized.

Provider-specific offsets should be explicit repository configuration, not inferred separately
from each response, so gap calculation is deterministic before provider access.

### Expand provider fetch windows around exact public ranges

Because public boundaries may be unaligned and provider schedules may be offset, an adapter fetch
window may need to begin before `from` and end after `to` to obtain every provider candle whose
open time falls in `[from, to)`.

The service derives provider fetch sections from the selected schedule. The adapter continues to
strictly filter normalized rows by the original public range before returning them.

Provider request limits are based on expected schedule slots plus a small boundary allowance, not
raw elapsed integer division.

Alternative considered: pass arbitrary boundaries directly and trust each provider. Provider
date-range semantics differ and may omit edge candles.

### Classify Twelve Data no-data responses inside the provider boundary

The custom Twelve Data HTTP client inspects structured error payloads before raising. A narrowly
recognized no-data condition from the time-series endpoint becomes a typed internal empty-result
signal or response that normalizes to zero rows.

All other error statuses remain failures. Classification uses structured status/code plus the
known no-data condition and is covered by fixture tests. Public responses never expose the raw
message.

Alternative considered: map every Twelve Data HTTP 400 to an empty result. That would hide invalid
symbols, bad intervals, entitlement problems, and malformed requests.

## Risks / Trade-offs

- **Provider candle offsets may differ by symbol, interval, exchange, or plan** → Keep schedule
  configuration explicit per provider/instrument class and verify fixtures for every supported
  timeframe; do not infer a universal Twelve Data offset from WTI hourly data alone.
- **A current-time boundary can include a forming candle** → Preserve existing completion logic;
  forming candles may be returned but are not persisted.
- **No-data classification depends on provider error behavior** → Match narrowly and retain
  sanitized failure behavior for unknown error payloads.
- **Schedule mistakes can cause repeated provider fills** → Add tests for persisted hit detection,
  edge ranges, offset candles, and natural provider gaps.
- **Clock-dependent tests can become flaky** → Inject a fixed request clock and assert the exact
  resolved response `to`.

## Migration Plan

1. Add optional-`to` request parsing with an injectable request clock.
2. Remove public alignment rejection and replace count validation with a ceiling-based upper bound.
3. Add candle schedule selection and migrate gap calculation to expected schedule opens.
4. Adapt provider fetch-window generation and preserve exact public-range filtering.
5. Add narrow Twelve Data no-data classification.
6. Update route, service, provider, integration, and contract tests.
7. Update OpenSpec and public API documentation.

No database migration is required. Rollback restores the required aligned `to` contract; clients
that adopted omitted or unaligned boundaries would need to send explicit aligned values again.

## Open Questions

- Before implementation, capture Twelve Data timestamps for all supported intervals of WTI, SPY,
  and QQQ. The observed hourly `:30` anchor must not be assumed for `1m`, `5m`, `15m`, or `1d`
  without evidence.
