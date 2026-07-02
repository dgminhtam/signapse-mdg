## ADDED Requirements

### Requirement: pandas-market-calendars is available as the calendar source

The project SHALL include `pandas-market-calendars` as a pinned dependency for future local calendar
session generation.

#### Scenario: Calendar package can be imported

- **WHEN** project dependencies are installed
- **THEN** `pandas_market_calendars` can be imported by project code
- **AND** no network access is required to inspect package calendar definitions at runtime

### Requirement: Supported market calendar types are seeded

The database SHALL seed reusable market calendar definitions for the currently supported asset
calendar families.

#### Scenario: Calendar type seed is applied

- **WHEN** the calendar type seed migration is applied
- **THEN** `market_calendars` contains `CRYPTO_24_7`
- **AND** it contains `FOREX_24_5`
- **AND** it contains `US_REGULAR`
- **AND** it contains `CME_ENERGY`
- **AND** it contains `CME_METALS`
- **AND** it contains `CME_AGRICULTURE`
- **AND** it contains `ICE_SOFTS`

#### Scenario: Calendar seed is repeated

- **WHEN** the calendar type seed operation encounters an existing calendar code
- **THEN** it updates the source metadata without creating duplicate rows

### Requirement: Supported symbols are mapped to seeded calendar types

The database SHALL assign calendar codes to currently supported symbols where the provider or proxy
calendar family is known.

#### Scenario: Symbol calendar mappings are seeded

- **WHEN** the calendar type seed migration is applied to a database containing the current symbol
  registry
- **THEN** `BTC/USD` and `ETH/USD` reference `CRYPTO_24_7`
- **AND** `EUR/USD`, `GBP/USD`, `USD/JPY`, `AUD/USD`, and `XAU/USD` reference `FOREX_24_5`
- **AND** `AAPL`, `TSLA`, `NVDA`, `MSFT`, `SPY`, `QQQ`, `SPX`, `NDX`, and `DJI` reference
  `US_REGULAR`
- **AND** `WTI`, `BRENT`, and `NATGAS` reference `CME_ENERGY`
- **AND** `XAG/USD` references `CME_METALS`
- **AND** `WHEAT` and `CORN` reference `CME_AGRICULTURE`
- **AND** `COFFEE` and `SUGAR` reference `ICE_SOFTS`

### Requirement: Calendar type seeding does not generate sessions

The calendar type seed change SHALL NOT create market calendar session rows or any calendar refresh
workflow.

#### Scenario: Calendar type seed completes

- **WHEN** the calendar type seed migration is applied
- **THEN** no `market_calendar_sessions` rows are inserted by this change
- **AND** no CLI, scheduler, or background job is required to complete application startup

### Requirement: Market-data behavior remains unchanged

Calendar type seeding SHALL NOT change quote, candle, stream, provider, cache, or public API
behavior.

#### Scenario: Existing APIs are used after calendar type seed

- **WHEN** the new dependency and calendar seed rows are present
- **THEN** public symbol responses keep the existing response shape
- **AND** historical candles continue to use the existing code-based market-session policies
- **AND** no request path uses `pandas_market_calendars` to decide candle eligibility in this change
