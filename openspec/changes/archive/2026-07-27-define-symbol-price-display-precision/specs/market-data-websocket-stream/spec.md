## ADDED Requirements

### Requirement: Stream market values are independent of display precision

The gateway SHALL serialize WebSocket quote prices and candle OHLCV values without rounding or
padding them according to symbol `price_display_decimals`, and SHALL not repeat display metadata
in stream events.

#### Scenario: Stream quote exceeds display decimals

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** a normalized stream quote price is `Decimal("2934.5678")`
- **THEN** the quote event contains `"price":"2934.5678"`
- **AND** it does not contain `priceDisplayDecimals`

#### Scenario: Stream candle exceeds display decimals

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** a normalized stream candle close is `Decimal("2934.5678")`
- **THEN** the candle event contains `"close":"2934.5678"`
- **AND** no candle OHLCV value is quantized from display metadata
- **AND** the event does not contain `priceDisplayDecimals`
