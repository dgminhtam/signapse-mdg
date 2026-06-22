## Why

Signapse now identifies Forex assets in the product catalog, but the gateway runtime still only
has Binance-backed crypto provider foundations and crypto-only registry seeds. Adding Twelve Data
as the Forex SDK foundation lets the project validate a lower-cost Forex data path before exposing
Forex through public quote, candle, or WebSocket contracts.

## What Changes

- Add Twelve Data as a configured provider SDK dependency and isolate it behind
  repository-owned provider adapter boundaries.
- Add typed Twelve Data settings for API key, base URL, and timeout policy without committing
  credentials.
- Add provider-foundation code for Forex REST capabilities needed later by quotes, candles, and
  symbol validation, but do not wire those capabilities into public `/v1/quotes`, `/v1/candles`,
  or `/v1/stream` behavior in this change.
- Seed the current Forex catalog assets into the PostgreSQL supported-symbol registry:
  `EUR/USD`, `GBP/USD`, `USD/JPY`, and `AUD/USD`.
- Keep WebSocket integration out of scope for this change; Twelve Data stream behavior and
  gateway realtime Forex candle policy will be handled separately.
- Preserve existing Binance crypto behavior and all existing public API response shapes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `provider-sdk-integration`: add Twelve Data SDK integration requirements for a Forex provider
  foundation while keeping SDK types behind `app/providers/`.
- `supported-symbol-registry`: extend required registry seeding to include the current Forex
  catalog symbols mapped to Twelve Data provider symbols.

## Impact

- Affects provider dependencies, provider adapter code, typed runtime configuration, environment
  examples, and provider-focused tests.
- Affects Alembic registry seed behavior and supported-symbol integration tests.
- Does not change successful public quote, candle, or WebSocket DTOs.
- Does not implement Forex HTTP quote/candle routing or Forex WebSocket streaming.
- Requires a deployment-provided Twelve Data API key before live Forex provider smoke tests can
  run.
