## MODIFIED Requirements

### Requirement: Required MVP symbols are seeded

The database migration SHALL seed exactly the required MVP symbol mappings without requiring
application startup.

#### Scenario: Initial seed is applied

- **WHEN** the migration is applied to an empty database
- **THEN** the registry contains enabled `BTC/USD` mapped to `TWELVE_DATA:BTC/USD`
- **AND** the registry contains enabled `ETH/USD` mapped to `TWELVE_DATA:ETH/USD`

#### Scenario: Seed operation is repeated

- **WHEN** the seed operation encounters either required mapping already present
- **THEN** it updates that mapping without creating a duplicate record

### Requirement: Enabled symbols can be listed

The gateway SHALL expose `GET /v1/symbols` and return only enabled registry records ordered by
canonical symbol ascending.

#### Scenario: Required symbols are enabled

- **WHEN** a client sends `GET /v1/symbols` after the initial migration
- **THEN** the gateway responds with HTTP status `200`
- **AND** the response contains `BTC/USD` with asset class `CRYPTO`, provider `TWELVE_DATA`,
  provider symbol `BTC/USD`, and enabled value `true`
- **AND** the response contains `ETH/USD` with asset class `CRYPTO`, provider `TWELVE_DATA`,
  provider symbol `ETH/USD`, and enabled value `true`
- **AND** the symbols are ordered by canonical symbol ascending

#### Scenario: A registry record is disabled

- **WHEN** a registry record has enabled value `false`
- **THEN** `GET /v1/symbols` omits that record

#### Scenario: No symbols are enabled

- **WHEN** the registry contains no enabled records
- **THEN** `GET /v1/symbols` responds with HTTP status `200`
- **AND** the response body is `{"symbols":[]}`

### Requirement: Current Forex catalog symbols are seeded

The database migration introduced by this change SHALL seed the current Forex catalog symbols as
enabled registry records mapped to the Twelve Data provider.

#### Scenario: Forex seed is applied to an upgraded database

- **WHEN** the database is upgraded through the Forex seed migration
- **THEN** the registry contains enabled `EUR/USD` with asset class `FOREX`, provider
  `TWELVE_DATA`, and provider symbol `EUR/USD`
- **AND** the registry contains enabled `GBP/USD` with asset class `FOREX`, provider
  `TWELVE_DATA`, and provider symbol `GBP/USD`
- **AND** the registry contains enabled `USD/JPY` with asset class `FOREX`, provider
  `TWELVE_DATA`, and provider symbol `USD/JPY`
- **AND** the registry contains enabled `AUD/USD` with asset class `FOREX`, provider
  `TWELVE_DATA`, and provider symbol `AUD/USD`
- **AND** the registry contains enabled `XAU/USD` with asset class `COMMODITY`, provider
  `TWELVE_DATA`, and provider symbol `XAU/USD`
- **AND** the registry contains enabled `AAPL`, `TSLA`, `NVDA`, and `MSFT` with asset class
  `US_STOCK`, provider `TWELVE_DATA`, and matching provider symbols
- **AND** existing `BTC/USD` and `ETH/USD` canonical rows remain enabled

#### Scenario: Forex seed operation is repeated

- **WHEN** the Forex seed operation encounters any required Forex mapping already present
- **THEN** it updates that mapping without creating a duplicate registry record

#### Scenario: Supported symbols are listed after Forex seed

- **WHEN** a client sends `GET /v1/symbols` after the Forex seed migration is applied
- **THEN** the response can include the enabled Forex records ordered by canonical symbol
  ascending with the existing symbol response shape
