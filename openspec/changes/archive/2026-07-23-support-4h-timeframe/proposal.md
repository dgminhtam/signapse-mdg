## Why

Clients cannot currently request a four-hour candle series consistently across the supported asset
catalog. Adding one canonical `4h` timeframe closes that contract gap for historical, realtime, and
backfill workflows.

## What Changes

- Add `4h` as a supported fixed-duration public candle timeframe for every enabled symbol.
- Route historical `4h` requests through the symbol's persisted provider adapter.
- Allow `4h` WebSocket subscriptions and derive or receive four-hour stream candles through the
  existing provider paths.
- Keep `h4` and other aliases unsupported.
- Update the public API documentation and automated coverage for the new timeframe.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `historical-candles`: Add `4h` to the supported fixed-duration timeframe contract for all enabled
  symbols and provider routes.
- `market-data-websocket-stream`: Add `4h` to the accepted stream timeframe contract and four-hour
  candle event behavior.

## Impact

The change affects the shared timeframe registry, REST provider interval maps, WebSocket timeframe
validation, the retained Binance stream interval map, tests, and `docs/spec.md`. It adds no database
migration, configuration, dependency, provider fallback, or cross-provider remapping.
