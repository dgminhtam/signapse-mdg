## Why

Signapse consumes MDG as an internal market-data service, and its WebSocket consumers primarily
render received prices. Requiring every consumer to separately load `/v1/symbols` and duplicate
rounding logic adds unnecessary coupling and can produce inconsistent display across HTTP and
WebSocket surfaces.

## What Changes

- **BREAKING** Format public price strings using each symbol's persisted
  `price_display_decimals`.
- Apply the same display formatting to latest quote prices, historical prices, historical candle
  OHLC fields, and WebSocket quote/candle price fields.
- Round with decimal `ROUND_HALF_UP` semantics and pad trailing zeros to exactly the configured
  number of fractional digits.
- Keep provider normalization, domain values, caches, candle aggregation, and persistence at their
  existing raw `Decimal` precision.
- Keep candle volume independent of price display precision.
- Keep existing response and event field sets unchanged; consumers receive formatted values in the
  existing price fields without needing a separate metadata event.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `supported-symbol-registry`: Define display precision as the formatting policy for public price
  serialization while preserving raw internal values.
- `latest-quotes`: Return latest quote `price` rounded and padded to the symbol's display precision.
- `historical-price`: Return historical `price` rounded and padded to the symbol's display
  precision.
- `historical-candles`: Format candle `open`, `high`, `low`, and `close` using symbol display
  precision without changing `volume`.
- `market-data-websocket-stream`: Format quote prices and candle OHLC fields before WebSocket
  delivery without adding per-event metadata.

## Impact

- Affects the shared decimal serialization boundary and the quote, candle, historical-price, and
  WebSocket response builders.
- Requires symbol display precision to remain available alongside service results and stream
  client registrations.
- Changes price strings observed by Signapse consumers, for example XAU/USD `2934.5678` becomes
  `"2934.57"` and `2934.5` becomes `"2934.50"`.
- Adds no dependency and does not alter database schemas, provider adapters, caches, or stored
  market data.
