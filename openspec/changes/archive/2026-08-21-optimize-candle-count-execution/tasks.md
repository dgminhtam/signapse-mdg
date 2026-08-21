## 1. Characterize the count contract

- [x] 1.1 Add service-level regression tests for latest, forward, and backward provider-backed
  count queries, including half-open cutoffs, ascending order, partial results, no synthetic rows,
  immutable Provider Selection, and completed-over-forming precedence.
- [x] 1.2 Add count-result boundary tests that assert `from` and `to` describe the actual Candle
  History Window scanned rather than unused fixed batch capacity.
- [x] 1.3 Add differential schedule tests that compare paged Eligible Candle Slots with existing
  schedule behavior across NYSE holidays, early closes, breaks, DST, provider offsets, fixed
  timeframes, and monthly timeframes.
- [x] 1.4 Preserve and run exact-range and slot-based `limit` regression tests to prove their
  missing-section behavior is unchanged.

## 2. Implement lazy count scheduling

- [x] 2.1 Introduce the private bounded count-page representation and directional cursor behavior
  used by Count Query Execution, including first-page and remaining-scan-budget limits.
- [x] 2.2 Extend the existing schedule and market-session boundaries to produce bounded count pages
  without materializing the full Candle Count Scan Budget.
- [x] 2.3 Implement in-process bulk session-window lookup and caching for calendar-backed policies
  while preserving all existing eligibility rules.
- [x] 2.4 Add unit coverage for page continuation, empty pages, closed sessions, and the retained
  10,000 Eligible Candle Slot scan budget.

## 3. Implement count-page materialization

- [x] 3.1 Add the internal Count Query Execution component and route only provider-backed `count`
  requests through it while preserving the existing public candle service interface.
- [x] 3.2 Implement persistence-first count-page loading and zero-provider-call behavior for fully
  persisted pages.
- [x] 3.3 Implement one logical contiguous provider fill for incomplete count pages, followed by
  eligibility filtering, canonical merge, and directional early stopping.
- [x] 3.4 Preserve forming-cache behavior, completed-over-forming precedence, provider-error
  propagation, and caller cancellation without starting later pages after cancellation.
- [x] 3.5 Add service tests for cold, warm, partially warm, sparse, and provider-failure count pages
  using the existing repository and provider fakes.

## 4. Adapt provider and persistence boundaries

- [x] 4.1 Verify and, where necessary, implement adapter-internal range chunking/paging for a
  logical count-page window without leaking Provider Identifier rules into Count Query Execution.
- [x] 4.2 Retain finite provider-operation timeouts and existing cancellation-safe shared-client
  behavior; do not add a request-level deadline or automatic retry policy.
- [x] 4.3 Replace per-candle completed persistence writes with an idempotent bulk upsert while
  retaining the existing provider-owned candle identity.
- [x] 4.4 Add repository and adapter contract tests for bulk upsert, provider range limits, normalized
  timestamp filtering, and no-fallback behavior.

## 5. Add diagnostics and documentation

- [x] 5.1 Emit safe structured count-execution diagnostics for page work, source row counts, stop
  reasons, and calendar/database/provider elapsed times.
- [x] 5.2 Add diagnostics tests for successful, partial, failed, and cancelled count execution,
  including Request ID correlation and sensitive-data exclusion.
- [x] 5.3 Update the product/API and system-design documentation to describe lazy count execution,
  actual scan-window response boundaries, and the distinction between Signapse caller timeout and
  finite provider-operation timeouts.

## 6. Validate and release

- [x] 6.1 Run provider compatibility probes for every affected Provider Selection, including
  SPY/YFinance hourly timestamp anchoring, wide-window behavior, paging, and schedule filtering.
- [x] 6.2 Run cold and warm benchmarks for representative count requests and record calendar, DB,
  provider, page, and provider-call measurements without adding a hard latency acceptance cutoff.
- [x] 6.3 Run the full test suite, lint, formatting, and static type checks.
- [x] 6.4 Deploy without a feature flag, monitor count diagnostics, and use normal deployment rollback
  if compatibility or correctness regressions are observed.
