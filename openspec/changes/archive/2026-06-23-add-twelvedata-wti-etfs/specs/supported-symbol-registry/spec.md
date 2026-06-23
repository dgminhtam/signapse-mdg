## ADDED Requirements

### Requirement: Validated WTI and ETF symbols are seeded

The database migration introduced by this change SHALL seed enabled WTI, SPY, and QQQ mappings
through the Twelve Data provider without changing existing registry mappings.

#### Scenario: New asset seed is applied
- **WHEN** the database is upgraded through the WTI and ETF seed migration
- **THEN** the registry contains enabled `WTI` with asset class `COMMODITY`, provider
  `TWELVE_DATA`, and provider symbol `WTI`
- **AND** the registry contains enabled `SPY` with asset class `ETF`, provider `TWELVE_DATA`, and
  provider symbol `SPY`
- **AND** the registry contains enabled `QQQ` with asset class `ETF`, provider `TWELVE_DATA`, and
  provider symbol `QQQ`
- **AND** existing enabled symbol mappings remain unchanged

#### Scenario: New asset seed is repeated
- **WHEN** the seed operation encounters an existing WTI, SPY, or QQQ canonical symbol
- **THEN** it restores the required mapping and enabled state without creating a duplicate record

#### Scenario: New asset seed is downgraded after a mapping was changed
- **WHEN** downgrade encounters a WTI, SPY, or QQQ row that no longer matches the seeded asset
  class, provider, or provider symbol
- **THEN** the migration leaves that changed row intact

### Requirement: ETF is a public registry asset class

The supported-symbol API SHALL expose `ETF` as the asset class for enabled ETF registry records.

#### Scenario: Seeded ETFs are listed
- **WHEN** a client sends `GET /v1/symbols` after the migration
- **THEN** the response includes `QQQ` and `SPY` with asset class `ETF`
- **AND** all enabled records remain ordered by canonical symbol ascending
