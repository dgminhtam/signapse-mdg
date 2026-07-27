## ADDED Requirements

### Requirement: Supported symbols define price display decimals

The gateway SHALL persist `price_display_decimals` for every supported symbol as an integer from
0 through 18 inclusive, SHALL require an explicit value, and SHALL NOT use it to constrain stored
or transported market-data precision.

#### Scenario: Display precision schema is migrated

- **WHEN** the database is upgraded through this change
- **THEN** `supported_symbols` contains a non-null `price_display_decimals` column
- **AND** the database rejects values below 0 or above 18
- **AND** the column has no default that silently assigns precision to a future symbol

#### Scenario: Existing catalog is backfilled

- **WHEN** the display precision migration is applied to the current supported-symbol catalog
- **THEN** `AUD/USD`, `EUR/USD`, and `GBP/USD` have value `5`
- **AND** `USD/JPY`, `XAG/USD`, and `NATGAS` have value `3`
- **AND** `BTC/USD`, `ETH/USD`, `XAU/USD`, `WTI`, `BRENT`, `COFFEE`, `SUGAR`, `WHEAT`,
  `CORN`, `AAPL`, `TSLA`, `NVDA`, `MSFT`, `SPY`, `QQQ`, `SPX`, `NDX`, and `DJI` have value `2`

#### Scenario: Future symbol omits display precision

- **WHEN** a new supported-symbol record is inserted without `price_display_decimals`
- **THEN** persistence rejects the record

### Requirement: Symbol API exposes price display decimals

The gateway SHALL expose each enabled symbol's persisted display precision as the integer
`priceDisplayDecimals` in `GET /v1/symbols`.

#### Scenario: Enabled symbol is listed

- **WHEN** a client sends `GET /v1/symbols`
- **THEN** every returned symbol contains `priceDisplayDecimals`
- **AND** the value matches that symbol's persisted `price_display_decimals`

#### Scenario: XAU display metadata is listed

- **WHEN** enabled `XAU/USD` has persisted `price_display_decimals` value `2`
- **AND** a client sends `GET /v1/symbols`
- **THEN** the `XAU/USD` object contains `"priceDisplayDecimals":2`

#### Scenario: Registry display precision changes

- **WHEN** an enabled symbol's persisted `price_display_decimals` value changes
- **THEN** a subsequent `GET /v1/symbols` response reflects the changed value
