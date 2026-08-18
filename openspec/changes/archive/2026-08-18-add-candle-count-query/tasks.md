## 1. Query contract and configuration

- [x] 1.1 Extend the candle request model and parser with optional `count` and an explicit count direction while preserving exact-range and slot-based `limit` modes.
- [x] 1.2 Validate integer `count` values in the inclusive range 1..1000 and reject `limit + count`, `from + to + count`, malformed values, and unsupported `before` requests with the documented HTTP 400 error.
- [x] 1.3 Add a typed internal count scan-budget setting with default 10,000 eligible slots and deployment-time validation; keep it out of the public query contract.
- [x] 1.4 Preserve the provider-agnostic response DTO and serialize resolved query boundaries without adding cursor or pagination metadata.

## 2. Count-mode scheduling and service behavior

- [x] 2.1 Add latest, forward, and backward count-mode scheduling over existing fixed-duration and calendar-month candle schedules, honoring market-session eligibility and strict `to` exclusivity.
- [x] 2.2 Implement bounded count scanning that stops when the requested row count, history exhaustion, or the configured eligible-slot scan budget is reached.
- [x] 2.3 Accumulate only Provider-backed Candle Snapshots, allowing provider/session gaps to produce partial results without synthetic OHLCV rows.
- [x] 2.4 Preserve exact-range purity and existing slot-based `limit` behavior, including their current response boundaries and maximum validation.
- [x] 2.5 Return valid empty or partial 200 responses for missing history while preserving sanitized provider-unavailable errors for provider failures.

## 3. Persistence, provider fill, and canonical merge

- [x] 3.1 Reuse repository-first reads and bounded provider gap fills while allowing count scans to inspect additional eligible slots beyond missing rows.
- [x] 3.2 Merge persistence, provider, and forming-cache results by unique `openTime`, prefer completed data over forming data, and ensure duplicates consume one count row.
- [x] 3.3 Include eligible forming snapshots in count results with `complete=false` without persisting them as completed candles.
- [x] 3.4 Ensure every candle-capable Provider Selection observes the same count semantics without automatic provider fallback.
- [x] 3.5 Audit provider-native range/page limits and add adapter-internal chunking only where required; keep provider models and errors behind the existing normalized boundary.

## 4. Contract and design documentation

- [x] 4.1 Update the historical candle API documentation with exact-range, slot-limit, and provider-backed-count query modes and their valid parameter combinations.
- [x] 4.2 Document that `limit` counts eligible timeframe slots while `count` is an upper bound on actual provider-backed rows and may return fewer rows.
- [x] 4.3 Document half-open boundaries, forming-candle inclusion, ascending ordering, deduplication, empty/error behavior, maximums, scan budget, and rejection of `before`.
- [x] 4.4 Document that MDG keeps exact ranges pure and that WS Java owns fallback, repeated requests, and merge policy.

## 5. Regression tests

- [x] 5.1 Add API/parser tests for latest, `from + count`, `to + count`, strict cutoff, malformed values, maximum values, conflicting parameters, and `before` rejection.
- [x] 5.2 Add service tests for fixed-duration and monthly count scheduling, session gaps, provider gaps, history exhaustion, and scan-budget partial responses.
- [x] 5.3 Add merge tests for unique `openTime`, completed-over-forming precedence, forming `complete=false`, ascending output, and no synthetic candles.
- [x] 5.4 Add provider-boundary tests confirming uniform count behavior, explicit provider failures, and no silent provider fallback.
- [x] 5.5 Retain and run regression coverage for exact ranges, `limit` slot semantics, half-open filtering, existing response shape, and current forming-cache behavior.

## 6. Verification

- [x] 6.1 Run the focused candle API and service test suites and confirm all new scenarios pass.
- [x] 6.2 Run the full pytest suite, lint/format checks, and static type checks.
- [x] 6.3 Review generated API/docs examples against the OpenSpec delta and confirm no WS or database migration work was introduced.
