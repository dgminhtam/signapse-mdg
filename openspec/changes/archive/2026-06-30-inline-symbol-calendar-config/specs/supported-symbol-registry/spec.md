## MODIFIED Requirements

### Requirement: Supported symbols can reference market calendars

The supported-symbol registry SHALL allow each symbol to store nullable inline market-calendar
configuration when a verified mapping exists.

#### Scenario: Registry calendar config columns are migrated

- **WHEN** the database is upgraded through this change
- **THEN** `supported_symbols` has nullable `calendar_source`, `calendar_name`, and
  `calendar_timezone` columns
- **AND** `supported_symbols` does not require `calendar_code` to reference a separate calendar
  table

#### Scenario: Obvious calendar config is seeded

- **WHEN** the migration runs against a database containing current supported symbol rows
- **THEN** Forex pairs and spot `XAU/USD` can store `pandas_market_calendars`, `FOREX`, and
  `America/New_York`
- **AND** US stocks, ETFs, and stock indexes can store `pandas_market_calendars`, `NYSE`, and
  `America/New_York`
- **AND** crypto symbols can store `internal`, `24/7`, and `UTC`
- **AND** verified futures proxy symbols can store their mapped `pandas_market_calendars` calendar
  names and time zones

#### Scenario: Public symbol response remains unchanged

- **WHEN** a client sends `GET /v1/symbols` after this migration
- **THEN** the response uses the existing supported-symbol response shape
- **AND** it does not expose `calendar_source`, `calendar_name`, or `calendar_timezone`
