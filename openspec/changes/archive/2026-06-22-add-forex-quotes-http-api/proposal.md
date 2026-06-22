## Why

The gateway can now seed Forex symbols and has a Twelve Data provider foundation, but
`GET /v1/quotes` still routes every supported symbol through the Binance-only quote provider.
Enabling Forex latest quotes lets clients request the current Forex catalog through the existing
minimal quote contract without waiting for candle or WebSocket support.

## What Changes

- Route `GET /v1/quotes` refreshes by each enabled symbol's persisted provider mapping instead of
  assuming a single Binance provider for all symbols.
- Enable Twelve Data latest-price refresh for seeded Forex symbols:
  `EUR/USD`, `GBP/USD`, `USD/JPY`, and `AUD/USD`.
- Preserve existing public quote response fields: `symbol`, `price`, and `receivedAt`.
- Preserve existing quote cache, request validation, per-symbol errors, and partial-success
  behavior.
- Keep Binance-backed crypto quote behavior unchanged for `BTC/USD` and `ETH/USD`.
- Keep `/v1/candles`, `/v1/stream`, and Twelve Data WebSocket integration out of scope.
- Treat missing or unusable Twelve Data configuration as a Forex provider failure without
  breaking crypto quote requests.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `latest-quotes`: extend latest quote behavior from Binance-only refreshes to provider-routed
  refreshes that support both Binance crypto and Twelve Data Forex through the same HTTP
  contract.

## Impact

- Affects quote service provider dispatch, quote route dependency wiring, and provider-focused
  tests.
- Affects runtime configuration behavior for Twelve Data quote enablement when a deployment
  supplies `TWELVEDATA_API_KEY`.
- Does not change public successful quote DTOs or request query shape.
- Does not add a database migration; it depends on the existing Forex seed migration.
- Does not implement Forex candles, WebSocket streaming, provider fallback, or aggregation.
