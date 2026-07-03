## Why

The ten enabled `YFINANCE` registry symbols are discoverable but cannot currently return data from
`GET /v1/quotes`. Enabling quote routing now lets the gateway serve those planned commodities and
stock indexes through the existing provider-agnostic contract while keeping candle and WebSocket
work separate.

## What Changes

- Add a repository-owned yfinance quote adapter for the ten seeded `YFINANCE` provider symbols.
- Use `Ticker.get_info()` and normalize `regularMarketPrice` as the latest provider price.
- Execute synchronous yfinance work outside the ASGI event loop with serialized shared-session
  access and deployment-controlled request timeouts.
- Route uncached `YFINANCE` symbols through the existing quote provider router, cache, freshness,
  partial-success, and sanitized-error behavior.
- Preserve the public `/v1/quotes` response shape and all existing Binance and Twelve Data routing.
- Keep yfinance historical candles and WebSocket streaming out of scope.
- Document that commodity mappings are futures proxies and that yfinance is an unofficial Yahoo
  Finance wrapper with operational and usage-policy constraints.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `latest-quotes`: Allow the ten enabled `YFINANCE` symbols to return normalized latest prices
  through the existing quote endpoint and provider-group isolation behavior.
- `provider-sdk-integration`: Define the yfinance quote adapter boundary, synchronous execution,
  timeout, concurrency, normalization, and failure-handling requirements while leaving candles and
  WebSocket streaming unwired.

## Impact

- Provider code gains a yfinance quote adapter and tests.
- Quote dependency wiring adds the `YFINANCE` provider without adding credentials or changing the
  public API schema.
- Existing `PROVIDER_HTTP_TIMEOUT_SECONDS`, quote cache TTL, stale threshold, and maximum-symbol
  settings remain the deployment controls.
- Documentation and OpenSpec contracts change from registry-only yfinance coverage to quote-enabled
  coverage for the ten seeded symbols.
