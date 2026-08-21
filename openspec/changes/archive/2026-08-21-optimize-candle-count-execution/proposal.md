## Why

Provider-backed candle `count` queries currently perform work proportional to the full Candle Count
Scan Budget rather than the requested Candle Count.  In particular, cold market-calendar queries
can spend more than the Signapse caller's current timeout constructing eligible slots, then issue
many serialized provider requests across closed market sessions.  The gateway should make the
count path efficient and bounded by data work while preserving its provider-agnostic candle
contract.

## What Changes

- Replace eager count-mode scan planning with lazy pages of Eligible Candle Slots, beginning with
  no more slots than the requested Candle Count and retaining the existing 10,000-slot Candle
  Count Scan Budget.
- Batch and cache market-session windows in process memory so calendar-backed schedules do not
  rebuild a provider calendar for each candidate slot.
- Load persistence once per count page and, when data is missing, request one logical contiguous
  provider window for that page instead of splitting it into per-session provider fills.
- Keep provider-native range limits, paging, finite operation timeouts, and client serialization
  inside selected provider adapters; do not introduce provider fallback or provider-specific
  branches in the count executor.
- Canonicalize page results by `openTime`, preserve completed-over-forming precedence, and bulk
  upsert completed candles.
- Clarify that count response boundaries describe the Candle History Window actually scanned.
- Add safe structured diagnostics for count-page work and require provider compatibility probes
  before rollout.
- Preserve the public response shape, immutable Provider Selection, no-synthetic-candle rule,
  existing provider-error behavior, exact-range behavior, and slot-based `limit` behavior.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `historical-candles`: Make provider-backed count execution lazy and page-oriented while
  preserving count semantics, and define count response boundaries from the actual scan window.
- `diagnostic-error-observability`: Record safe count-execution stage and work metrics in
  structured diagnostics.

## Impact

- Affects candle request orchestration, candle schedules and market-session policies, provider
  adapters, persistence writes, forming-cache interaction, configuration, and candle tests.
- Does not add an HTTP endpoint, query parameter, response field, database migration, calendar
  table, runtime feature flag, total MDG request deadline, or automatic provider fallback.
- Signapse owns its end-to-end timeout configuration; this change reduces MDG work but does not
  make caller timeout a gateway data-contract rule.
