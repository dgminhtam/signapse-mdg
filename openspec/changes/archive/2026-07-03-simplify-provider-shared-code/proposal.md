## Why

Provider adapter code now repeats the same decimal parsing, timeframe duration lookup, and SDK
client construction patterns across Binance, Twelve Data, and yfinance. The duplication makes
small provider behavior changes easier to miss and adds lines without changing the gateway
contract.

## What Changes

- Reuse shared provider normalization helpers for Decimal parsing where provider behavior matches.
- Reuse canonical timeframe duration data from `app.domain.timeframes` instead of per-provider
  duplicate duration maps.
- Collapse duplicate Binance REST SDK client construction into one internal helper.
- Collapse duplicate yfinance provider builder functions where they construct the same provider.
- Remove tiny stream-provider redundancies that add no behavior, including a one-line alias and a
  duplicated symbol lookup loop.
- Simplify WebSocket route registry mapping that rechecks fields already guaranteed by the symbol
  repository contract.
- Preserve all public HTTP/WebSocket contracts, persistence behavior, provider allowlists, and
  error boundaries.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `provider-sdk-integration`: Provider adapters keep the same external behavior while sharing
  common internal normalization and provider setup code where rules are identical.

## Impact

- Affected production code: `app/providers/`, selected provider wiring in `app/api/`, and a small
  registry mapping cleanup in `app/api/routes_stream.py`.
- Affected tests: existing unit tests for provider normalization, provider builders, route wiring,
  and stream providers should continue to pass with no contract updates.
- No database migration, dependency change, public API change, or OpenAPI response change.
