## Why

Clients currently receive exact decimal strings but have no gateway-owned rule for how many
fractional digits to display per symbol. This causes inconsistent presentation, such as `XAU/USD`
showing four decimals when the product convention is two.

## What Changes

- Persist a required `price_display_decimals` value for every supported symbol.
- Backfill explicit display precision for all 24 currently enabled symbols.
- Expose the value as `priceDisplayDecimals` from `GET /v1/symbols`.
- Require future supported-symbol records to define their display precision explicitly.
- Keep quote prices, historical prices, candle OHLCV values, cached values, persisted values, and
  WebSocket events at their normalized source precision; consumers use registry metadata only
  when rendering prices.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `supported-symbol-registry`: Persist, validate, seed, and expose price display decimals for every
  supported symbol.
- `latest-quotes`: Clarify that display metadata does not round or pad returned quote prices.
- `historical-candles`: Clarify that display metadata does not alter returned or persisted candle
  values.
- `historical-price`: Clarify that display metadata does not alter the selected candle close.
- `market-data-websocket-stream`: Clarify that display metadata does not alter quote or candle
  event values.

## Impact

- Adds one constrained column and a data backfill to `supported_symbols`.
- Extends the supported-symbol domain model, SQLAlchemy model, repository mapping, and
  `GET /v1/symbols` response.
- Requires downstream display clients to cache symbol metadata and format prices at render time.
- Does not add dependencies or change provider adapters, caches, candle persistence, quote/candle
  response shapes, or WebSocket event shapes.
