## MODIFIED Requirements

### Requirement: Historical price values are independent of display precision

The gateway SHALL retain the selected one-minute candle close at its persisted precision and SHALL
serialize the public historical `price` rounded with `ROUND_HALF_UP` and padded to exactly the
symbol's `price_display_decimals`.

#### Scenario: Selected close exceeds display decimals

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** the selected one-minute candle close is `Decimal("2934.5678")`
- **THEN** the historical price response contains `"price":"2934.57"`
- **AND** the persisted candle close remains unchanged

#### Scenario: Selected close is exactly halfway

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** the selected one-minute candle close is `Decimal("2934.565")`
- **THEN** the historical price response contains `"price":"2934.57"`

#### Scenario: Historical price response remains minimal

- **WHEN** a historical price is returned successfully
- **THEN** the response continues to contain exactly `symbol`, `price`, and `pricedAt`
- **AND** it does not contain `priceDisplayDecimals`
