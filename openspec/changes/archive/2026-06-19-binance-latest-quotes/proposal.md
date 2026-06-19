## Why

The gateway currently exposes its supported symbol registry but cannot return market prices.
Adding Binance-backed latest quotes completes the first usable market-data flow for the required
`BTC/USD` and `ETH/USD` pairs while keeping the scope limited to one HTTP endpoint.

## What Changes

- Add `GET /v1/quotes?symbols=...` for one or more canonical symbols.
- Validate requested symbols against the PostgreSQL-backed enabled symbol registry.
- Fetch missing quotes from the Binance Spot public `GET /api/v3/ticker/price` batch endpoint.
- Normalize prices as decimal strings and return gateway receive time, nullable provider time,
  nullable volume, and freshness state.
- Add a process-local quote cache with configurable TTL and stale threshold.
- Return successful quotes and per-symbol errors in the same well-formed multi-symbol response.
- Add typed Binance REST, timeout, cache, freshness, and request-size settings.
- Keep candles, WebSocket streaming, persistence of quotes, authentication, provider fallback,
  and all other market-data endpoints out of scope.

## Capabilities

### New Capabilities

- `latest-quotes`: Defines validation, Binance retrieval, normalization, caching, freshness, and
  partial-error behavior for `GET /v1/quotes`.

### Modified Capabilities

None.

## Impact

- Adds quote domain models, provider and cache boundaries, a market-data service, and a quotes
  API route.
- Uses the existing supported-symbol PostgreSQL repository without changing its schema.
- Moves the locked HTTPX dependency into runtime dependencies for outbound async HTTP.
- Adds outbound HTTPS calls to the configurable Binance Spot REST base URL.
- Adds unit and integration coverage for provider normalization, cache behavior, validation,
  partial failures, and the HTTP contract.
