## Why

Sparse session or provider data can make a valid candle range return fewer candles, or an empty
result, even when usable historical observations exist before the requested window. The existing
`limit` parameter bounds timeframe-slot scanning rather than actual candle rows, so it cannot
express the chart client's need for up to N provider-backed snapshots without changing exact-range
behavior.

## What Changes

- Add a public `count` query mode for requesting up to a bounded number of actual provider-backed
  candle snapshots.
- Support latest, forward-from-`from`, and backward-before-`to` count anchors with strict
  half-open timestamp semantics.
- Preserve `limit` as the existing eligible-slot query mode and document that it does not guarantee
  `candles.length == limit`.
- Bound `count` at 1,000 rows and add a separate internal eligible-slot scan budget for sparse data.
- Return partial valid results when the scan budget is reached; never synthesize OHLCV candles.
- Reject ambiguous `count` combinations and unsupported `before` requests with HTTP 400.
- Preserve the provider-agnostic response shape, ascending order, forming-candle behavior, and
  explicit provider-error handling.
- Keep fallback selection, repeated requests, and merge policy in the WS Java consumer rather than
  adding fallback behavior to the exact-range MDG contract.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `historical-candles`: extend the existing candle query contract with actual-row `count` modes,
  scan-budget behavior, validation, and the clarified distinction between `limit` slots and
  provider-backed candle snapshots.

## Impact

- The historical candle HTTP query contract gains the `count` parameter and new validation rules.
- Candle request parsing and the application service must select actual-row count targets while
  preserving existing exact-range and slot-limit modes.
- Schedule, persistence, forming-cache, provider-fill, and merge paths must support scanning past
  missing eligible slots and deduplicating by `openTime`.
- Provider adapters remain behind the existing normalized candle boundary; no provider identity is
  exposed publicly and no automatic provider fallback is introduced.
- API and service regression tests must cover sparse assets, gaps, forming snapshots, empty history,
  provider failures, query-mode validation, maximums, ordering, and synthetic-candle prevention.
- No WS API, cursor, response metadata, or UI behavior is changed by this MDG proposal.
