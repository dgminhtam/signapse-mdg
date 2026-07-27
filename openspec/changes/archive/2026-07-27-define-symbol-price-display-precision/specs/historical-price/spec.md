## ADDED Requirements

### Requirement: Historical price values are independent of display precision

The gateway SHALL serialize the selected one-minute candle close without rounding or padding it
according to symbol `price_display_decimals`, and SHALL keep display metadata out of the minimal
historical-price response.

#### Scenario: Selected close exceeds display decimals

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** the selected one-minute candle close is `Decimal("2934.5678")`
- **THEN** the historical price response contains `"price":"2934.5678"`
- **AND** the gateway does not change it to `"2934.57"`

#### Scenario: Historical price response remains minimal

- **WHEN** a historical price is returned successfully
- **THEN** the response continues to contain exactly `symbol`, `price`, and `pricedAt`
- **AND** it does not contain `priceDisplayDecimals`
