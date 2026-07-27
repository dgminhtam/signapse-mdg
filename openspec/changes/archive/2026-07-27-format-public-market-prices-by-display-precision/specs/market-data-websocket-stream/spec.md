## MODIFIED Requirements

### Requirement: Stream market values are independent of display precision

The gateway SHALL retain normalized WebSocket quote and candle values internally, SHALL serialize
quote prices and candle OHLC fields with `ROUND_HALF_UP` rounding and exact padding according to
symbol `price_display_decimals`, SHALL leave candle volume at raw precision, and SHALL not repeat
display metadata in stream events.

#### Scenario: Stream quote exceeds display decimals

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** a normalized stream quote price is `Decimal("2934.5678")`
- **THEN** the quote event contains `"price":"2934.57"`
- **AND** it does not contain `priceDisplayDecimals`

#### Scenario: Stream candle exceeds display decimals

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** a normalized stream candle has OHLC values with more than two fractional digits
- **THEN** every candle OHLC field is rounded and padded to exactly two fractional digits
- **AND** the event's volume remains the raw fixed-point decimal string
- **AND** the event does not contain `priceDisplayDecimals`

#### Scenario: Stream price requires trailing-zero padding

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** a normalized stream price is `Decimal("2934.5")`
- **THEN** the corresponding public price field is `"2934.50"`
