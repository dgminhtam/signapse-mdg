## Why

Signapse has a planned asset catalog that is not yet backed by any market-data provider. Adding
yfinance as a locked provider dependency and seeding only those unbacked assets lets the team test
catalog coverage and provider-symbol fit before wiring public quote, candle, or WebSocket behavior.

## What Changes

- Add the `yfinance` Python package as a project dependency for future provider adapter work.
- Introduce `YFINANCE` as a persisted provider identifier for registry rows.
- Seed the currently unbacked planned assets with yfinance provider symbols:
  - `XAG/USD -> SI=F`
  - `BRENT -> BZ=F`
  - `SPX -> ^GSPC`
  - `NDX -> ^NDX`
  - `DJI -> ^DJI`
  - `NATGAS -> NG=F`
  - `COFFEE -> KC=F`
  - `SUGAR -> SB=F`
  - `WHEAT -> ZW=F`
  - `CORN -> ZC=F`
- Add `STOCK_INDEX` as a public registry asset class for index rows.
- Keep all quote, candle, and WebSocket market-data routing unchanged in this change.
- Document that commodity yfinance symbols are futures or rolling-futures proxies, not spot
  instruments.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `provider-sdk-integration`: add the yfinance dependency and provider-boundary rules while keeping
  SDK usage out of non-provider layers.
- `supported-symbol-registry`: seed the unbacked planned assets as enabled `YFINANCE` registry
  records and expose `STOCK_INDEX` through the existing symbol-list response.

## Impact

- Project dependencies and lockfile.
- Alembic migrations for supported-symbol registry seeding.
- Supported-symbol domain/schema validation if asset classes are constrained.
- `/v1/symbols` documentation and tests for the newly seeded registry rows.
- No public latest quote, historical candle, or WebSocket provider routing changes.
