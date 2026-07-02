## Why

Supported symbols now carry inline calendar metadata, but candle eligibility still relies on hard-coded
asset-class policies. Using those symbol calendar configs lets the gateway filter historical and stream
candles with the same local calendar source selected per asset.

## What Changes

- Extend internal `SupportedSymbol` values and repository mapping to carry inline calendar config.
- Route existing market-session checks through inline calendar config before falling back to the
  current asset-class policies.
- Add a minimal `pandas_market_calendars` policy for supported exchange calendars, using cached local
  schedules.
- Keep `CRYPTO_24_7` and Forex/XAU weekly quote-session behavior on internal policies where that is
  more correct than the package calendar.
- Preserve current public API response shapes.
- Do not add generated calendar sessions, scheduler, background refresh, or new database tables.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `historical-candles`: candle expected-open calculation, provider fill, persistence, and cache merge use inline symbol calendar config for market-session eligibility.
- `market-data-websocket-stream`: stream candle derivation, market-closed status, cache update, and persistence handoff use inline symbol calendar config for market-session eligibility.

## Impact

- Affected code: symbol domain model, symbol repositories, market-session policy selection, candle schedule tests, candle service tests, stream tests.
- Affected dependency: uses already-pinned `pandas-market-calendars`.
- No public HTTP or WebSocket response shape changes.
- No migration, scheduler, or materialized calendar-session storage.
