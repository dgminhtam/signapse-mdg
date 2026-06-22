## ADDED Requirements

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
- **AND** existing `BTC/USD` and `ETH/USD` crypto mappings remain enabled and unchanged

#### Scenario: Forex seed operation is repeated

- **WHEN** the Forex seed operation encounters any required Forex mapping already present
- **THEN** it updates that mapping without creating a duplicate registry record

#### Scenario: Supported symbols are listed after Forex seed

- **WHEN** a client sends `GET /v1/symbols` after the Forex seed migration is applied
- **THEN** the response can include the enabled Forex records ordered by canonical symbol
  ascending with the existing symbol response shape

### Requirement: Forex registry seeding does not enable Forex market data APIs

Seeding Forex symbols SHALL NOT change public quote, candle, or WebSocket market-data behavior in
this change.

#### Scenario: Public data APIs are used after Forex seed

- **WHEN** the Forex registry rows exist
- **THEN** existing Binance-backed crypto quote, candle, and stream behavior remains unchanged
- **AND** no Twelve Data provider call is made by public quote, candle, or WebSocket routes until
  a later provider-routing change explicitly enables it
