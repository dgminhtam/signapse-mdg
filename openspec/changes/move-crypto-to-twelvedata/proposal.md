## Why

`BTC/USD` and `ETH/USD` currently route through Binance Spot `BTCUSD` and `ETHUSD`, whose historical
coverage is too short for the gateway's monthly candle use case. Twelve Data already carries the
gateway's broader market-data catalog, so moving these canonical crypto symbols there gives
consistent historical coverage while keeping provider details behind the registry.

## What Changes

- Change the required seed mapping for `BTC/USD` and `ETH/USD` to `TWELVE_DATA` with matching
  provider symbols `BTC/USD` and `ETH/USD`.
- Keep the Binance provider implementation available, but stop using it as the default persisted
  mapping for these two canonical symbols.
- Allow the Twelve Data REST and stream adapters to serve `BTC/USD` and `ETH/USD`.
- Update tests and docs that currently assert the Binance crypto mapping.
- Document the required database data update for existing deployments.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `supported-symbol-registry`: Required crypto seed rows change from `BINANCE_SPOT` provider
  symbols to `TWELVE_DATA` provider symbols.
- `latest-quotes`: Quote refreshes for `BTC/USD` and `ETH/USD` use their persisted Twelve Data
  mapping.
- `historical-candles`: Candle fills for `BTC/USD` and `ETH/USD` use their persisted Twelve Data
  mapping.
- `market-data-websocket-stream`: Stream subscriptions for `BTC/USD` and `ETH/USD` route through
  their persisted Twelve Data mapping.
- `provider-sdk-integration`: Twelve Data adapters support the two crypto provider symbols.

## Impact

- Affected code: supported-symbol seed migration, Twelve Data supported-symbol allowlist, docs, and
  focused tests for symbols, quotes, candles, and streams.
- Public APIs: response shapes stay unchanged; `provider` and `providerSymbol` returned by
  `/v1/symbols` change for `BTC/USD` and `ETH/USD`.
- Database: existing `supported_symbols` rows for `BTC/USD` and `ETH/USD` must be updated in place;
  historical candle rows under the old Binance identity remain stored but are no longer reused by
  the new mapping.
- Dependencies: no new dependencies.
