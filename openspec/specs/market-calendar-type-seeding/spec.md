# Market Calendar Type Seeding Specification

## Purpose

Define dependency and seed data requirements for inline supported-symbol calendar metadata.

## Requirements

### Requirement: pandas-market-calendars is available as the calendar source

The project SHALL include `pandas-market-calendars` as a pinned dependency for local calendar
schedule evaluation.

#### Scenario: Calendar package can be imported

- **WHEN** project dependencies are installed
- **THEN** `pandas_market_calendars` can be imported by project code
- **AND** no network access is required to inspect package calendar definitions at runtime

### Requirement: Supported symbols are seeded with inline calendar config

The database SHALL assign inline calendar source metadata to currently supported symbols where the
provider or proxy calendar family is known.

#### Scenario: Inline calendar config seed is applied

- **WHEN** the inline calendar config seed migration is applied to a database containing the current
  registry
- **THEN** `BTC/USD` and `ETH/USD` store `internal`, `24/7`, and `UTC`
- **AND** `EUR/USD`, `GBP/USD`, `USD/JPY`, `AUD/USD`, and `XAU/USD` store
  `pandas_market_calendars`, `FOREX`, and `America/New_York`
- **AND** `AAPL`, `TSLA`, `NVDA`, `MSFT`, `SPY`, `QQQ`, `SPX`, `NDX`, and `DJI` store
  `pandas_market_calendars`, `NYSE`, and `America/New_York`
- **AND** `WTI`, `BRENT`, and `NATGAS` store `pandas_market_calendars`,
  `CMEGlobex_Energy`, and `America/New_York`
- **AND** `XAG/USD` stores `pandas_market_calendars`, `CMEGlobex_Metals`, and
  `America/New_York`
- **AND** `WHEAT` and `CORN` store `pandas_market_calendars`, `CMEGlobex_Grains`, and
  `America/Chicago`
- **AND** `COFFEE` and `SUGAR` store `pandas_market_calendars`, `ICEUS`, and
  `America/New_York`

### Requirement: Calendar type seeding does not generate sessions

The inline calendar config seed change SHALL NOT create market calendar session rows or any
calendar refresh workflow.

#### Scenario: Inline calendar config seed completes

- **WHEN** the inline calendar config seed migration is applied
- **THEN** no `market_calendar_sessions` rows are inserted by this change
- **AND** no CLI, scheduler, or background job is required to complete application startup

### Requirement: Market-data behavior remains unchanged

Inline calendar config seeding SHALL NOT change quote, candle, stream, provider, cache, or public API
behavior.

#### Scenario: Existing APIs are used after inline calendar config seed

- **WHEN** the new dependency and inline calendar config values are present
- **THEN** public symbol responses keep the existing response shape
- **AND** historical candles continue to use the existing code-based market-session policies
- **AND** no request path uses `pandas_market_calendars` to decide candle eligibility in this change
