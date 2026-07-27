## ADDED Requirements

### Requirement: Candle values are independent of display precision

The gateway SHALL preserve normalized and persisted candle OHLCV values independently of symbol
`price_display_decimals`, and SHALL NOT add display metadata to the historical candle response.

#### Scenario: Candle OHLC has more fractional digits than display metadata

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** a normalized candle contains close value `Decimal("2934.5678")`
- **THEN** the gateway stores and returns the close without display-driven quantization
- **AND** the public close value is `"2934.5678"`

#### Scenario: Candle response shape remains unchanged

- **WHEN** historical candles are returned successfully
- **THEN** the response and each candle continue to contain only their documented fields
- **AND** neither contains `priceDisplayDecimals`

#### Scenario: Volume is unaffected

- **WHEN** a candle is normalized, persisted, or returned
- **THEN** `price_display_decimals` is not applied to its volume
