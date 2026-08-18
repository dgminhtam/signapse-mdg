## Context

The historical candle service currently derives eligible timeframe opens from the symbol's
schedule, reads complete candles from persistence, fills missing sections through the selected
provider, merges forming snapshots, and filters the response back to the derived opens. This is a
good fit for exact ranges and for the existing `limit` modes, where `limit` bounds eligible slots.

It is not sufficient for sparse assets when the caller needs a number of actual provider-backed
rows. A provider or session gap can consume eligible slots without producing a candle, so changing
the meaning of `limit` would break existing callers and would make the exact-range contract less
predictable.

The change is constrained by the existing provider-selection boundary: one request resolves one
immutable Provider Selection, and the service must not silently use another provider. It also
preserves the provider-agnostic candle response and the existing forming-snapshot behavior.

## Goals / Non-Goals

**Goals:**

- Add an explicit `count` query mode for up to a bounded number of actual provider-backed candle
  snapshots.
- Support latest, forward-from-`from`, and backward-before-`to` anchors with UTC half-open
  semantics.
- Keep exact ranges pure and preserve the existing slot-based `limit` modes.
- Bound sparse-data work with a separate eligible-slot scan budget.
- Preserve response shape, ordering, forming-candle behavior, provider isolation, and no-synthetic
  data guarantees.
- Make invalid query combinations and unsupported `before` usage explicit HTTP 400 errors.

**Non-Goals:**

- Changing `limit` from slot-based semantics to actual-row semantics.
- Adding a `before` endpoint, cursor pagination, or response metadata.
- Implementing WS Java fallback, merge, or chart-display logic.
- Generating synthetic candles or automatically switching providers.
- Adding database migrations or changing the public candle response schema.

## Decisions

### Use a separate `count` parameter

`limit` remains the compatibility-preserving eligible-slot bound. `count` is a distinct actual-row
bound with these modes:

- `count`: latest provider-backed snapshots before one captured request-time boundary.
- `from + count`: provider-backed snapshots with `openTime >= from`, moving forward.
- `to + count`: provider-backed snapshots with `openTime < to`, moving backward.

`from + to + count` and `limit + count` are invalid. This is preferred over changing `limit`
because existing clients may rely on its slot-derived response window and because an actual-row
query must search beyond missing eligible slots.

Alternatives considered:

- Reinterpret `limit` as actual rows: rejected because it is a breaking semantic change and makes
  existing slot-window behavior unpredictable.
- Add `before`: rejected because `to + count` expresses the required cutoff without a second
  backward-specific parameter.
- Add a cursor: deferred until clients need long-running pagination or explicit continuation
  metadata.

### Scan eligible slots and accumulate actual rows

The candle service remains the orchestration boundary. For a count request it will derive eligible
opens from the existing schedule and market-session policy, walk in the requested direction, and
accumulate unique provider-backed snapshots until one of these conditions occurs:

1. The requested `count` is reached.
2. The available history is exhausted.
3. The configured count scan budget is reached.

Persistence lookup, provider fill, forming-cache merge, and provider normalization continue to use
the existing boundaries. Missing eligible opens remain missing. A provider adapter may internally
chunk or page a bounded range to honor its own API limits, but the public contract remains
provider-agnostic.

The public maximum for `count` is 1,000 rows. The separate initial scan budget is 10,000 eligible
slots and is an internal setting, not a query parameter. A scan-budget stop returns the rows found
so far as a valid partial response; it never expands into unbounded work or fabricates rows.

Alternatives considered:

- Reuse the 1,000-slot request bound as the scan budget: rejected because a sparse series could
  exhaust the same bound before finding a useful number of actual rows.
- Scan without a bound until `count` is reached: rejected because provider latency and request
  volume would be unbounded for sparse or exhausted history.

### Preserve half-open boundaries and resolved response boundaries

`from` is inclusive and `to` is exclusive for all modes. A backward count excludes a candle whose
`openTime` equals `to`. The response continues to expose only `symbol`, `timeframe`, `from`, `to`,
and `candles`; its `from` and `to` describe resolved query boundaries, not an inferred data extent.

No `hasMoreBefore`, `nextBefore`, actual-data extent, or reason-for-partial field is added. A
consumer can use returned candle open times to issue another request when it owns continuation
logic.

### Canonicalize rows before counting

Rows from persistence, provider fills, and the forming cache are merged by unique `openTime`.
Completed snapshots take precedence over forming snapshots for the same open time. The final
response is sorted ascending by `openTime`, even for a backward query.

This reuses the existing repository/provider-owned candle model and prevents duplicate rows from
consuming the requested count.

### Keep empty and provider failure outcomes distinct

A valid count query with no matching provider-backed history returns HTTP 200 with an empty candle
list. A valid query that finds fewer rows returns the available partial result. Provider timeout,
rate-limit, transport, configuration, or normalization failures continue through the sanitized
provider-unavailable boundary and are never converted to an empty result.

Unsupported `before`, malformed count values, count values outside 1..1000, and ambiguous mode
combinations return HTTP 400 without provider or persistence work where validation can reject them
first.

### Apply the contract uniformly across selected providers

All candle-capable provider mappings use the same count semantics. Provider-specific range limits,
chunking, and normalization remain inside adapters. The request's selected Provider Selection is
fixed for the whole operation; no automatic provider fallback is introduced.

## Risks / Trade-offs

- [Sparse history can still produce fewer than `count`] → Return an explicit valid partial response,
  keep a bounded scan budget, and leave continuation decisions to WS.
- [Large count scans can increase provider latency] → Cap rows at 1,000, cap eligible-slot scans at
  the internal budget, batch contiguous missing sections, and retain existing provider timeouts.
- [A provider's native range or page limit may be smaller than a scan batch] → Let each adapter
  chunk internally while preserving the normalized provider boundary.
- [Clients may assume `candles.length == count`] → Document that `count` is an upper bound and add
  regression tests for provider/session gaps and scan-budget partial results.
- [Forming and completed data can overlap during refresh] → Merge by `openTime` and prefer the
  completed snapshot.
- [Rejecting `before` can expose previously ignored client typos] → Return a documented 400 instead
  of silently interpreting the request as another mode.

## Migration Plan

1. Add the `count` query contract and internal scan-budget setting while leaving exact and `limit`
   requests unchanged.
2. Implement request validation, count-mode scheduling, row accumulation, canonical merge, and
   provider-agnostic response handling.
3. Add API/service regression coverage and update the historical candle documentation and examples.
4. Deploy without a database migration; existing clients continue using the old modes.
5. Roll back by disabling/reverting `count` acceptance if needed; exact-range and `limit` behavior
   remain independently usable.

## Open Questions

No blocking product or contract questions remain. The initial scan-budget value is an operational
default that can be tuned without changing the public `count` semantics.
