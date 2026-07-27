## Why

The normalized provider-mapping table currently contains only the legacy mapping copied for each
asset, so it does not represent the approved provider configuration for the 24-asset catalog. The
gateway needs a deterministic seed that records one default provider per asset and the five
approved inactive yfinance alternatives without introducing fallback behavior.

## What Changes

- Seed the approved 24-asset catalog as 29 normalized provider mappings: 24 active defaults and
  five inactive yfinance alternatives.
- Keep `XAU/USD` mapped only to `TWELVE_DATA:XAU/USD`; do not seed `GC=F` or another yfinance proxy.
- Set `ETH/USD` to active `BINANCE_SPOT:ETHUSD` with inactive `YFINANCE:ETH-USD`.
- Set `AAPL`, `BTC/USD`, `EUR/USD`, and `QQQ` to their active Twelve Data mappings with inactive
  yfinance alternatives.
- Set the remaining 18 assets to the approved active yfinance symbols.
- Mirror each active default into the temporary legacy `supported_symbols.provider` and
  `supported_symbols.provider_symbol` columns so the deployed runtime continues to route all three
  market-data paths consistently.
- Expand the repository-owned yfinance allowlist to cover the approved yfinance symbols used by
  the seed.
- Preserve manual selection semantics: no request-time fallback, priority, or per-route provider
  choice.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `supported-symbol-registry`: Define the exact default and additional provider mappings seeded for
  the 24 supported assets.
- `latest-quotes`: Allow every active yfinance-backed asset in the approved catalog to use the
  existing quote endpoint.
- `historical-candles`: Allow every active yfinance-backed asset in the approved catalog to use the
  existing candle endpoint.
- `provider-sdk-integration`: Expand the approved yfinance provider-symbol allowlist consistently
  across quote, candle, and stream adapters.

## Impact

- Adds one Alembic seed revision after `20260727_0018`.
- Updates `supported_symbols` legacy provider values and `symbol_provider_mappings` seed rows.
- Updates the shared yfinance provider-symbol allowlist and its adapter tests.
- Adds PostgreSQL migration coverage for fresh upgrade, repeatability, preservation of unknown
  custom mappings, downgrade behavior, and the exact 24-active/5-inactive approved seed.
- Does not change public API shapes, add fallback, migrate candle identity, or remove legacy
  provider columns.
