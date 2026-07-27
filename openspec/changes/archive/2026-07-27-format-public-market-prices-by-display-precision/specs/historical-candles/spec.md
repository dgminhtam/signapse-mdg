## MODIFIED Requirements

### Requirement: Candle values are independent of display precision

The gateway SHALL preserve normalized and persisted candle OHLCV values independently of symbol
`price_display_decimals`, SHALL serialize public candle `open`, `high`, `low`, and `close` with
`ROUND_HALF_UP` rounding and exact fractional-digit padding, and SHALL leave `volume` independent
of price display precision.

#### Scenario: Candle OHLC has more fractional digits than display metadata

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** a normalized candle contains `open`, `high`, `low`, and `close` values with more than two
  fractional digits
- **THEN** each public OHLC field is rounded with `ROUND_HALF_UP` and contains exactly two
  fractional digits
- **AND** the normalized and persisted OHLC values remain unchanged

#### Scenario: Candle response shape remains unchanged

- **WHEN** historical candles are returned successfully
- **THEN** the response and each candle continue to contain only their documented fields
- **AND** neither contains `priceDisplayDecimals`

#### Scenario: Volume is unaffected

- **WHEN** a candle is normalized, persisted, or returned
- **THEN** `price_display_decimals` is not applied to its volume
- **AND** the public volume remains the raw fixed-point decimal string
