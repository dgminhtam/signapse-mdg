## Why

The gateway already exposes provider-agnostic historical candles and has a Twelve Data Forex
time-series adapter foundation, but `/v1/candles` still sends every cache miss to Binance.
Enabling Forex candle routing completes the REST market-data path for the seeded Forex catalog
without waiting for Twelve Data WebSocket support.

## What Changes

- Route `/v1/candles` provider fills by the enabled symbol's persisted provider mapping.
- Keep `BTC/USD` and `ETH/USD` candle behavior on the Binance Spot adapter.
- Enable Twelve Data historical candles for `EUR/USD`, `GBP/USD`, `USD/JPY`, and `AUD/USD`.
- Preserve the existing request shape, minimal response fields, PostgreSQL-first gap fill,
  completion calculation, and candle persistence identity.
- Adapt the gateway's half-open `[from,to)` range to Twelve Data's time-series request boundaries
  and reject out-of-range provider rows.
- Normalize missing Forex volume to decimal zero because the public candle contract requires a
  volume field and Twelve Data Forex may omit it.
- Preserve natural Forex market gaps without synthesizing OHLCV candles.
- Treat missing or unusable Twelve Data configuration as a sanitized provider-unavailable error
  for affected Forex candle requests without breaking crypto candles or application startup.
- Keep `/v1/stream` and Twelve Data WebSocket integration out of scope.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `historical-candles`: extend historical candle provider fills from Binance-only behavior to
  registry-routed Binance crypto and Twelve Data Forex behavior.

## Impact

- Affects candle provider dependency wiring, provider routing, Twelve Data time-series range
  normalization, tests, and candle documentation.
- Reuses the existing Forex registry seed, Twelve Data SDK dependency, candle table, cache, and
  repository; no database migration or public API field change is required.
- Live Forex candle fills require `TWELVEDATA_API_KEY`; crypto candle requests remain usable
  without that credential.
- Does not add Forex WebSocket streams, provider fallback, provider aggregation, synthetic candles,
  or market-calendar persistence.
