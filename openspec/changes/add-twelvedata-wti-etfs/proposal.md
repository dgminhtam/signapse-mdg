## Why

The product catalog identifies WTI crude oil, SPY, and QQQ as supported assets, but the gateway
registry and Twelve Data runtime allowlist do not currently expose them. The provider symbols
`WTI`, `SPY`, and `QQQ` have now been validated against Twelve Data, so the gateway can close this
catalog-to-runtime gap.

## What Changes

- Seed enabled `WTI`, `SPY`, and `QQQ` registry mappings through an idempotent Alembic migration.
- Classify `WTI` as `COMMODITY` and `SPY`/`QQQ` as `ETF`, all mapped to provider `TWELVE_DATA`
  with provider symbols matching their canonical symbols.
- Generalize the existing Twelve Data adapter and symbol allowlist beyond its Forex-oriented
  naming so the new assets can use the existing quote, historical candle, and WebSocket routes.
- Add market-session policies for US ETFs and WTI rather than treating either asset class as
  continuously open.
- Preserve the existing provider-agnostic public quote, candle, and stream event shapes.
- Update the public supported asset-class contract and catalog/runtime documentation.
- Add migration, provider normalization, routing, market-session, REST, and stream coverage for the
  three new assets.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `supported-symbol-registry`: require enabled Twelve Data registry mappings for WTI, SPY, and QQQ
  and expose `ETF` as a supported asset class.
- `provider-sdk-integration`: extend the official Twelve Data SDK adapter boundary from the current
  Forex/metal/stock allowlist to the validated commodity and ETF symbols.
- `latest-quotes`: allow WTI, SPY, and QQQ quote refreshes through their persisted Twelve Data
  mappings.
- `historical-candles`: allow WTI, SPY, and QQQ historical candle retrieval with asset-appropriate
  market-session filtering.
- `market-data-websocket-stream`: allow WTI, SPY, and QQQ realtime quote and derived candle streams
  through the shared Twelve Data WebSocket connection with market-closed semantics.

## Impact

- Adds one Alembic seed migration after revision `20260622_0006`.
- Affects Twelve Data REST/WebSocket adapters, provider naming and allowlists, market-session
  policies, application wiring, and tests.
- Expands `GET /v1/symbols` with three enabled records and adds `ETF` to documented asset-class
  values.
- Does not change public quote, candle, error, or WebSocket event field shapes.
- Requires a valid Twelve Data entitlement for live WTI, SPY, and QQQ provider access.
