## Why

The gateway already persists complete candles on demand, but first user requests still pay the
provider latency and cost for cold or partially missing ranges. A small backfill CLI can pre-warm
`market_data_candles` using the same repository-first gap-fill behavior before traffic arrives.

## What Changes

- Add an internal candle backfill command that fills configured historical ranges for enabled
  symbols and supported timeframes.
- Reuse the existing candle repository, provider router, schedule, market-session, normalization,
  completion, and idempotent upsert behavior.
- Split long ranges into bounded chunks instead of bypassing `MAX_CANDLES_PER_REQUEST`.
- Fetch only missing eligible ranges and leave already persisted complete candles untouched.
- Keep user-facing HTTP and WebSocket contracts unchanged.

## Capabilities

### New Capabilities
- `candle-backfill`: Internal CLI-driven candle backfill into `market_data_candles`.

### Modified Capabilities
- None.

## Impact

- Affected code: new CLI module, dependency wiring helpers if needed, focused unit/integration
  coverage.
- Affected systems: PostgreSQL candle persistence and configured market-data providers.
- Public APIs: none.
- Dependencies and migrations: none.
