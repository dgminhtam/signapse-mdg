## Why

The new `YFINANCE` assets already exist in the registry and latest quote path, but clients still
cannot request normalized historical candles for those symbols. Adding candle support lets the
gateway serve the planned commodity and stock-index assets through the same provider-agnostic
`GET /v1/candles` contract used by existing Binance and Twelve Data symbols.

## What Changes

- Add `YFINANCE` historical candle routing for the existing seeded symbols:
  `XAG/USD`, `BRENT`, `NATGAS`, `COFFEE`, `SUGAR`, `WHEAT`, `CORN`, `SPX`, `NDX`, and `DJI`.
- Add a yfinance candle adapter behind `app/providers/` that uses the locked `yfinance`
  dependency to fetch history and normalize rows into gateway-owned candle models.
- Preserve the existing `/v1/candles` response shape, half-open UTC range semantics, cache-first
  persistence flow, and provider-unavailable error boundary.
- Preserve natural provider gaps and never synthesize missing yfinance candles.
- Keep yfinance WebSocket or realtime candle streaming out of scope for this change.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `historical-candles`: Enable existing `YFINANCE` registry mappings to use `GET /v1/candles`
  through the persisted provider routing path.
- `provider-sdk-integration`: Extend yfinance provider-boundary requirements from quote-only
  access to include historical candle fetching and normalization while keeping WebSocket routing
  out of scope.

## Impact

- Affected API: `GET /v1/candles` accepts the existing enabled `YFINANCE` symbols when a candle
  fill is needed.
- Affected code: candle provider router, yfinance provider adapter, timeframe/history mapping,
  market-session eligibility, candle normalization, and related dependency wiring.
- Affected persistence: no schema change expected; fetched complete candles continue to upsert
  into `market_data_candles` using `(provider, provider_symbol, timeframe, open_time)`.
- Affected tests: yfinance adapter unit tests, candle router/service tests, route contract tests,
  and import-boundary coverage for yfinance.
