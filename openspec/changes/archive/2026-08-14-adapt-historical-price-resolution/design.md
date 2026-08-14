## Context

Historical Price Resolution currently enters the existing candle flow through
`HistoricalPriceService`, while `CandleService` owns Provider Selection, market-session eligibility,
persistence-first reads, provider fills, normalization, and cache merging. The historical-price
service already has a policy seam and can reuse a resolved symbol while attempting multiple
timeframes.

The current resolution is effectively one-minute-only for the default service path. Provider
history retention, natural gaps, and closed sessions can therefore produce no result even when a
completed coarser candle is available. Provider mappings are request-scoped and the accepted ADR
forbids automatic provider fallback, so adaptive resolution must remain inside one immutable
Provider Selection.

## Goals / Non-Goals

**Goals:**

- Add deterministic adaptive resolution for every selected provider.
- Prefer the finest available canonical resolution while preventing look-ahead.
- Reuse the existing candle service and provider adapter boundaries.
- Distinguish valid no-data from operational provider failures.
- Make the selected resolution explicit in successful responses.
- Preserve existing persistence, cache, market-session, decimal, and error-envelope behavior.

**Non-Goals:**

- Cross-provider fallback, aggregation, or provider equivalence selection.
- Runtime-configurable ladders or hard-coded provider retention settings.
- Raw tick lookup, local candle synthesis, or resampling.
- Changes to the public candle endpoint or candle storage schema.
- New provider integrations or dynamic capability discovery.

## Decisions

### One orchestration seam

`HistoricalPriceService` owns the resolution loop and delegates every candidate to the existing
`CandleService`. The service resolves Provider Selection once, then passes the same resolved mapping
through every attempt. No new capability protocol or provider router is introduced.

Each attempt uses the candle service's backward count flow with a bounded request for recent
candidates. The historical service selects the latest returned eligible candle whose `close_time`
is at or before the requested `at`. This lets the existing schedule handle offset hourly candles,
weekends, holidays, and maintenance breaks without a second calendar implementation.

Alternative: add a historical-price-specific repository/provider search loop. Rejected because it
duplicates the existing schedule, persistence, and gap-fill behavior.

### Fixed canonical ladder

The resolver tries `1m`, `5m`, `1h`, and `1d` in that order, sequentially, with at most four
attempts. It stops at the first eligible result. The ladder is code-defined rather than an
environment setting because it is API semantics and must be deterministic across deployments.

Provider adapters retain responsibility for mapping canonical timeframes to native intervals. A
provider can naturally return no data for an unsupported or unavailable range; the resolver then
tries the next ladder entry.

Alternative: maintain separate fully independent ladders per provider. Rejected for the initial
implementation because all current providers expose the selected canonical intervals and a common
ordering is simpler to test and explain.

### No-data versus operational failure

An adapter returns an empty candle list for a valid request with no available rows, including
retention limits, natural gaps, and recognized no-data responses. Timeouts, credentials, quotas,
rate limits, transport failures, malformed payloads, and invalid provider responses remain
`ProviderUnavailableError` and terminate resolution immediately.

Alternative: retry a coarser timeframe after every provider exception. Rejected because it masks
outages and can return a misleading low-resolution price while the selected provider is unhealthy.

### Completed-candle and no-lookahead rule

The selected candle must be complete and satisfy `close_time <= at`. A candle that opens before
`at` but closes after it is rejected, including daily/hourly candles that contain the instant.
`pricedAt` remains the selected candle's `open_time`, while `resolution` identifies the candle's
granularity.

Alternative: return the close of the candle containing `at`. Rejected because it uses future data
for any request inside a coarser candle.

### Public response contract

Successful historical-price responses contain exactly `symbol`, `price`, `pricedAt`, and
`resolution`. `resolution` uses canonical values `1m`, `5m`, `1h`, or `1d`. Provider-native names,
fallback reasons, and provider identity remain internal.

The selected candle's open timestamp continues to be serialized as `pricedAt` to preserve the
existing meaning. The new `resolution` field makes the precision of a fallback explicit.

Alternative: expose only the existing three fields. Rejected because clients could not distinguish
an exact one-minute price from a daily fallback.

### Future timestamp validation

The request captures the current UTC instant once. `at > now` is rejected as
`INVALID_TIME_RANGE`; `at == now` follows the completed-candle rule. This prevents the endpoint
from presenting a current value as a historical price for a future instant.

Alternative: allow future timestamps and return the latest known completed candle. Rejected because
that behavior is surprising for a historical endpoint and hides caller errors.

### Persistence and cache reuse

Every resolution attempt uses the existing candle flow. Complete fetched candles are persisted and
cached under their actual timeframe and Provider Selection. A `5m`, `1h`, or `1d` candle is never
relabeled as `1m`.

Alternative: keep coarse fallback results transient for historical-price only. Rejected because it
repeats provider calls and bypasses the existing persistence guarantee.

### Sequential execution

Attempts are sequential and stop on the first result. Parallel attempts are not used because they
spend provider quota and latency on resolutions that may never be needed. The four-attempt bound
keeps worst-case work predictable.

## Risks / Trade-offs

- **Coarser results are less precise** → expose the selected canonical `resolution` and keep the
  finest-first ordering.
- **A no-data response can be provider-specific** → keep classification inside adapters and cover
  recognized no-data and operational-error paths with provider tests.
- **A request may make up to four provider calls** → stop immediately on success and cap attempts
  at the fixed ladder length.
- **Provider retention rules can change** → avoid hard-coded age thresholds; rely on adapter
  no-data behavior and update adapter tests when upstream contracts change.
- **Strict future rejection may affect existing callers** → document the validation in the API
  contract and return the existing stable `INVALID_TIME_RANGE` error.
- **Daily session close remains based on existing candle/session semantics** → do not add new
  exchange-close modeling in this change; revisit only if observed product requirements demand it.

## Migration Plan

1. Update the historical-price domain result and HTTP DTO to include canonical `resolution`.
2. Replace the one-minute-only default policy with the fixed sequential ladder.
3. Add future timestamp validation using one captured UTC clock value.
4. Update provider adapters and tests so valid no-data remains empty while operational failures
   remain unavailable-provider errors.
5. Add service, API, provider, and provider-mapping integration coverage.
6. Update product/spec/design documentation and generated API expectations.
7. Deploy as a code-only change; no database migration is required.

Rollback is code-only: restore the previous one-minute resolver and three-field response contract.
Existing coarse candle rows remain valid and can be reused by a later deployment.

## Open Questions

None for this change. A future change may add a caller-selected maximum acceptable resolution, but
that is intentionally not part of this public contract.
