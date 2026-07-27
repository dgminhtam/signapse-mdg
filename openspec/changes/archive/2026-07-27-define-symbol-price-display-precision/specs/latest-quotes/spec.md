## ADDED Requirements

### Requirement: Latest quote values are independent of display precision

The gateway SHALL serialize latest quote prices from their normalized `Decimal` values without
rounding or padding them according to symbol `price_display_decimals`, and SHALL keep display
metadata out of the minimal quote response.

#### Scenario: Quote has more fractional digits than its display metadata

- **WHEN** `XAU/USD` has `price_display_decimals` value `2`
- **AND** its normalized latest quote price is `Decimal("2934.5678")`
- **THEN** the public quote price is `"2934.5678"`
- **AND** the gateway does not change the value to `"2934.57"`

#### Scenario: Quote response remains minimal

- **WHEN** a successful latest quote is returned
- **THEN** it continues to contain exactly `symbol`, `price`, and `receivedAt`
- **AND** it does not contain `priceDisplayDecimals`
