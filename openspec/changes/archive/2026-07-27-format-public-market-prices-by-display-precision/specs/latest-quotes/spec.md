## MODIFIED Requirements

### Requirement: Latest quote values are independent of display precision

The gateway SHALL retain latest quote prices internally as normalized `Decimal` values and SHALL
serialize the public `price` rounded with `ROUND_HALF_UP` and padded to exactly the symbol's
`price_display_decimals`.

#### Scenario: Quote has more fractional digits than its display metadata

- **WHEN** `XAU/USD` has `price_display_decimals` value `2`
- **AND** its normalized latest quote price is `Decimal("2934.5678")`
- **THEN** the public quote price is `"2934.57"`
- **AND** the internally normalized quote remains `Decimal("2934.5678")`

#### Scenario: Quote requires trailing-zero padding

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** its normalized latest quote price is `Decimal("2934.5")`
- **THEN** the public quote price is `"2934.50"`

#### Scenario: Quote response remains minimal

- **WHEN** a successful latest quote is returned
- **THEN** it continues to contain exactly `symbol`, `price`, and `receivedAt`
- **AND** it does not contain `priceDisplayDecimals`
