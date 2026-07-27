## MODIFIED Requirements

### Requirement: Supported symbols define price display decimals

The gateway SHALL persist `price_display_decimals` for every supported symbol as an integer from
0 through 18 inclusive, SHALL require an explicit value, and SHALL use it only when serializing
public price fields without constraining provider-normalized, cached, aggregated, or persisted
market-data precision.

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

#### Scenario: Market value is held internally

- **WHEN** a provider-normalized price has more fractional digits than its symbol display precision
- **THEN** domain values, caches, candle aggregation, and persistence retain the normalized value
- **AND** display rounding occurs only when a public price field is serialized
