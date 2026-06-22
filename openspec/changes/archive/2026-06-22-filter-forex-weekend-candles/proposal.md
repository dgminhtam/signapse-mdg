## Why

Twelve Data returns indicative Forex candles throughout Saturday and Sunday, while Signapse wants
broker-style charts containing only the normal weekly Forex quote session. Keeping those candles
would distort chart continuity, indicators, signals, and backtests compared with common MT5/broker
behavior.

## What Changes

- Define a Signapse weekly Forex quote session from Sunday 17:00 through Friday 17:00 in
  `America/New_York`.
- Apply the weekly session to all enabled assets whose persisted asset class is `FOREX`.
- Exclude closed-session Forex candles returned by providers, loaded from PostgreSQL, or found in
  the current-candle cache.
- Split Forex provider gap fills into open-session ranges so the gateway does not request the
  closed weekend interval.
- Keep crypto and all non-Forex candle behavior unchanged.
- Handle New York daylight-saving transitions through timezone-aware rules rather than fixed UTC
  offsets.
- Remove already persisted closed-session Forex candles through a targeted data-cleanup migration.
- Keep holiday closures, early closes, provider maintenance windows, quotes, and WebSocket
  filtering out of scope.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `historical-candles`: make historical Forex candle retrieval, gap detection, normalization,
  persistence, and response merging aware of the Signapse weekly quote session.

## Impact

- Affects candle-domain session policy, `CandleService` gap calculation and merge behavior, Twelve
  Data Forex normalization, candle persistence cleanup, tests, and documentation.
- Adds an Alembic data-cleanup migration but does not change the candle table schema or public API
  contract.
- Uses the Python standard library `zoneinfo` with the portable `tzdata` database so
  `America/New_York` works consistently on Windows and Linux.
- Does not implement holiday calendars, market-state APIs, provider-specific schedules, Forex quote
  filtering, or Twelve Data WebSocket support.
