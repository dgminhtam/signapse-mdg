## Context

Provider-backed candle `count` queries currently construct the entire Candle Count Scan Budget of
Eligible Candle Slots before accessing persistence or a selected provider.  Calendar-backed
symbols such as SPY can spend most of a request rebuilding market sessions one candidate at a
time.  The first count batch is then split at market closures into many provider fetch sections,
which are performed serially by adapters with shared-client serialization.

Signapse, not MDG, owns the observed end-to-end timeout.  This change therefore reduces the work
performed by a valid MDG request; it does not introduce a gateway-wide elapsed-time cutoff.  The
existing Historical Candles contract already distinguishes valid partial count results caused by
history or Candle Count Scan Budget exhaustion from provider failures, and it requires one
immutable Provider Selection, no synthetic candles, and a provider-agnostic response.

The implementation crosses candle orchestration, scheduling, market-session calculation,
persistence, forming cache behavior, provider adapters, and diagnostics.  It must preserve
exact-range and slot-based `limit` behavior.

## Goals / Non-Goals

**Goals:**

- Make count-mode work proportional to pages actually needed to find the requested Candle Count.
- Remove repeated per-candidate calendar construction from calendar-backed count traversal.
- Replace per-session provider fan-out in count mode with one logical contiguous fill per
  incomplete page.
- Preserve all existing count semantics: directional anchors, half-open boundaries, immutable
  Provider Selection, no fallback, no synthetic data, canonical merge precedence, and valid
  partial results only for data/budget outcomes.
- Persist completed page results efficiently and make count-stage work observable.
- Keep the public endpoint, request parameters, response shape, and provider adapter boundary
  stable.

**Non-Goals:**

- Changing exact-range or `limit` scheduling/fill behavior.
- Adding a request-level MDG deadline, time-based partial result, latency SLO contract, automatic
  retry policy, provider fallback, or public continuation metadata.
- Materializing exchange calendars in the database, adding a migration, or adding a runtime
  feature flag.
- Redesigning single-flight scope, globally parallelizing provider work, or adding a provider
  capability registry.

## Decisions

### Use one internal Count Query Execution boundary

The candle service remains the public orchestration and validation boundary.  It delegates only
provider-backed count requests to one internal Count Query Execution component, which returns the
existing candle result model.  That component owns directional page traversal, persistence-first
materialization, provider hydration, canonical merge, result boundary tracking, and stopping.

Existing Candle Schedule, Market Session Policy, candle repository, forming cache, and provider
adapter boundaries remain dependencies beneath it.  A new protocol, count-specific repository, or
count-specific provider port is not introduced because each would initially have only one useful
implementation.

Alternative considered: modify the shared range/limit fill path in place.  Rejected because
fine-grained missing-section behavior remains useful for exact ranges and slot limits, while count
needs different paging and early-stop behavior.

### Generate Eligible Candle Slots lazily in bounded pages

The first page contains at most the requested Candle Count and the existing provider-safe page
capacity of 999 slots.  Later pages are produced only when previous pages did not yield enough
unique Provider-backed Candle Snapshots, each at most 999 slots and never beyond the remaining
10,000-slot Candle Count Scan Budget.

Forward traversal starts at the inclusive `from` anchor.  Backward traversal starts strictly
before the exclusive `to` anchor.  Results are always returned in ascending order.  Response
boundaries describe the Candle History Window actually consumed by the pages, rather than an
unused fixed-size batch.

Alternative considered: retain one eager 10,000-slot tuple and only change provider batching.
Rejected because it leaves the calendar cost and event-loop blocking root cause intact.

### Batch calendar sessions in the existing market-session boundary

Calendar-backed policies obtain a bounded session window in one calendar operation and cache that
window in process memory by calendar and time segment.  Slot enumeration is then performed from
the cached sessions, preserving regular closes, early closes, session breaks, holidays, DST, and
provider-specific schedule offsets.  Fixed-duration and calendar-month schedule behavior remains
available through the existing schedule boundary.

The cache is an optimization only; process restart may discard it without changing correctness.

Alternative considered: persist calendar sessions in PostgreSQL.  Rejected because bulk calendar
queries already remove the measured bottleneck without new data ownership, refresh logic, or a
migration.

### Materialize each count page through one contiguous provider window

For every page, complete candles are loaded from persistence first and filtered to the page's
Eligible Candle Slots.  If the page is incomplete, Count Query Execution requests one logical
contiguous Candle History Window from the fixed Provider Selection, even when it crosses a closed
market interval.  Normalized provider rows are filtered back to eligible opens before merging.

This intentionally may refetch some already persisted rows in a partially warm page.  The trade is
accepted because one broad request avoids potentially hundreds of serialized per-session
requests, while canonical merge and idempotent persistence preserve correctness.  A fully warm
page makes no provider call.  A closed-only page makes no provider call.

Provider-native range ceilings, pagination, SDK client serialization, and finite operation
timeouts remain inside the existing provider adapters.  The count component neither selects a
different provider nor knows provider-specific range rules.

Alternative considered: retain precise missing sections for count mode.  Rejected because market
closures make that strategy the primary source of cold-path fan-out.  Alternative considered:
move provider capabilities into the service.  Rejected because it leaks adapter policy into a
provider-agnostic layer.

### Preserve canonical snapshot and persistence semantics

All page sources are keyed by `openTime`.  Completed persisted or fetched candles take precedence
over a forming snapshot for the same open.  A duplicate consumes one Candle Count row.  Completed
candles are bulk-upserted for a page using the existing provider-owned candle identity; forming
snapshots retain their current process-local cache behavior.

Alternative considered: make cache and persistence interchangeable through a new generic store.
Rejected because their durability, completion, and failure semantics are intentionally different.

### Keep failure, timeout, cancellation, and concurrency policies distinct

There is no total MDG request deadline and no elapsed-time-based partial response.  Signapse owns
the end-to-end caller timeout.  Finite provider-operation timeouts remain necessary to prevent an
individual upstream call from hanging indefinitely.  Provider failures remain sanitized provider
errors even when prior pages found data; only history/data gaps or scan-budget exhaustion produce
a valid partial response.

Caller cancellation propagates into count execution.  No later page or provider fill starts after
cancellation, while already-running synchronous provider work follows its adapter's
cancellation-safe behavior.

The current series-level single-flight behavior is retained in phase 1.  Global parallel fetches
and narrower page locks are deferred because they would introduce cache/provider races and do not
address the measured root cause.

### Make count execution diagnosable and gate rollout on provider compatibility

Structured diagnostics record Request ID, Provider Selection, symbol, timeframe, direction,
Eligible Candle Slots scanned, page count, provider call count, source row counts, stop reason,
and calendar/DB/provider elapsed times.  Fields remain internal and log-safe.

Before release, compatibility probes validate each relevant selected provider's timestamp anchor,
wide-range behavior, internal paging, schedule filtering, and no-fallback behavior.  SPY with its
YFinance Provider Selection is an explicit probe target.

Alternative considered: add a runtime feature flag.  Rejected because it preserves two divergent
count execution paths and the legacy path is the problem being removed; normal deployment rollback
is simpler.

## Risks / Trade-offs

- [A broad fill refetches persisted rows on partially warm pages] → Filter, canonicalize, and
  idempotently bulk-upsert rows; accept the modest overfetch to remove high round-trip latency.
- [Provider range limits differ by adapter] → Keep chunking inside adapters and require
  compatibility probes before rollout.
- [YFinance timestamps may not match an assumed hourly anchor] → Validate actual normalized
  timestamps and schedule filtering for SPY/YFinance before release.
- [Calendar optimization could alter edge-case eligibility] → Differential-test page output against
  existing schedule behavior for holidays, breaks, DST, offsets, and monthly timeframes.
- [No total MDG deadline permits a slow but valid request to run longer than a caller expects] →
  Signapse controls caller timeout; retain finite provider-operation timeouts, cancellation, scan
  budget, and structured diagnostics.
- [Bulk upsert may differ across test and production database dialects] → Test idempotent complete
  candle persistence through the repository boundary in supported environments.
- [Actual scan-window response boundaries are observable] → Specify and regression-test the new
  boundary rule for count mode.
- [Retained single-flight can still queue unrelated count requests for a series] → Measure lock
  wait through diagnostics and consider narrower work sharing only as a later change.

## Migration Plan

1. Add regression and differential tests that pin current public count semantics and calendar
   eligibility before changing execution.
2. Implement lazy scheduling, calendar session caching, count-page materialization, adapter-safe
   logical fills, bulk persistence, and diagnostics behind the count-only internal boundary.
3. Run provider compatibility probes and cold/warm benchmarks, including SPY/YFinance hourly
   behavior.
4. Deploy normally after probe and test success; Signapse may independently adjust its caller
   timeout as planned.
5. Monitor safe count diagnostics after deployment.  If a correctness or operational regression is
   found, roll back the deployment; no data migration or feature-flag state must be reversed.

## Open Questions

No blocking design decisions remain.  The exact adapter-safe range chunk sizes and observed
benchmark values are provider-specific release inputs, not new public contract choices.
