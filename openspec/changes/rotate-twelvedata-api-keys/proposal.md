## Why

Twelve Data is the first provider in this gateway that depends on a configured API key for live
REST fills and streams. Supporting multiple Twelve Data keys gives operations a small resilience
and throughput lever when a key hits rate limits or is temporarily unusable, without introducing
multi-provider fallback.

## What Changes

- Add deployment configuration for multiple Twelve Data API keys while preserving the existing
  single-key setting as a compatible input.
- Rotate Twelve Data REST requests across configured healthy keys inside the Twelve Data provider
  boundary.
- Put keys that fail with provider quota/auth style errors on a short process-local cooldown and
  try at most one alternate key for the same operation.
- Keep Twelve Data SDK imports, clients, key selection, and sanitized error handling inside
  `app/providers/`.
- Keep WebSocket behavior simple: choose one configured key when the stream connects or reconnects;
  do not rotate a live WebSocket subscription.
- Do not change Binance, yfinance, persisted provider mappings, public API responses, or database
  schema.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `provider-sdk-integration`: Twelve Data provider configuration and adapter behavior support
  multiple configured API keys for Twelve Data only.

## Impact

- Affected code: typed settings, Twelve Data REST provider factory/adapter, Twelve Data stream
  provider factory, route/backfill wiring, environment docs, focused tests.
- Public APIs: none.
- Database/migrations: none.
- Other providers: none.
