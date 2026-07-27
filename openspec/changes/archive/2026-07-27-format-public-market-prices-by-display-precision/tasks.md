## 1. Shared Price Formatting

- [x] 1.1 Add a shared API price formatter that rounds `Decimal` values with `ROUND_HALF_UP` and
  pads fixed-point output to exactly 0 through 18 configured fractional digits, while retaining
  the existing raw decimal formatter for volume.
- [x] 1.2 Add focused formatter tests for rounding down, halfway rounding up, trailing-zero
  padding, and representative 2-, 3-, and 5-decimal symbol policies.

## 2. Precision Context Propagation

- [x] 2.1 Carry persisted `price_display_decimals` alongside quote, candle, and historical-price
  service result context without changing raw `Quote` or `Candle` values.
- [x] 2.2 Retain a symbol-to-display-precision map on each WebSocket client registration using the
  registry rows already resolved during subscription.

## 3. Public HTTP and WebSocket Serialization

- [x] 3.1 Format latest quote and historical-price `price` fields with their symbol precision while
  preserving their existing response shapes.
- [x] 3.2 Format historical candle `open`, `high`, `low`, and `close` fields with symbol precision,
  leaving `volume` on the raw fixed-point serializer.
- [x] 3.3 Format WebSocket quote `price` and candle OHLC fields from registration precision context,
  leaving volume raw and preserving the exact existing event field sets.

## 4. Contract Verification and Documentation

- [x] 4.1 Replace raw-transport regression expectations with exact formatted HTTP and WebSocket
  examples, including XAU/USD rounding and padding, and prove cached, aggregated, and persisted
  domain values remain unchanged.
- [x] 4.2 Update `docs/spec.md`, `docs/assets.md`, and `docs/system-design.md` to document MDG-owned
  display formatting, `ROUND_HALF_UP`, HTTP/WebSocket consistency, raw internal values, and raw
  candle volume.
- [x] 4.3 Run `uv run pytest`, `uv run ruff check .`, `uv run mypy app`, and strict OpenSpec
  validation.
