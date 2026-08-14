## Why

The historical-price endpoint currently depends on one-minute history, but provider retention
limits, natural gaps, and closed sessions can make that resolution unavailable even when a usable
completed coarser candle exists. The endpoint needs deterministic adaptive resolution so valid
historical lookups do not fail solely because fine-grained provider history is missing.

## What Changes

- Add a fixed historical resolution ladder: `1m`, `5m`, `1h`, then `1d`.
- Resolve attempts sequentially within the immutable Provider Selection, stopping at the first
  eligible completed candle.
- Permit fallback only for valid empty/no-data results; operational provider and database failures
  remain errors and are not masked.
- Require the selected candle to have `close_time <= at` so coarser candles cannot look ahead.
- Add required public `resolution` metadata to successful historical-price responses. **BREAKING**
- Keep `pricedAt` as the selected candle open timestamp.
- Reject future `at` timestamps with `INVALID_TIME_RANGE`. **BREAKING**
- Reuse existing candle persistence, cache, market-session, normalization, and provider-routing
  behavior for every attempted resolution.
- Keep provider-native interval names, retention handling, and no-data classification inside
  provider adapters.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `historical-price`: Extend the response contract with `resolution`; define the fixed adaptive
  resolution ladder, sequential fallback, completed-candle/no-lookahead selection, future timestamp
  validation, and no-data versus operational failure behavior.

## Impact

- Updates the historical-price service result and HTTP response DTO.
- Updates provider adapter handling so valid no-data or retention responses remain empty results,
  while operational failures remain unavailable-provider errors.
- Reuses the existing candle service, repository, cache, provider selection, and market-session
  boundaries; no new persistence schema or dependency is required.
- Requires unit, API, provider, and provider-mapping integration coverage for all supported
  Provider Selections.
- Requires updates to the historical-price OpenSpec delta, product contract, system design, and
  implementation task list.
