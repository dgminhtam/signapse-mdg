## ADDED Requirements

### Requirement: Supported symbols can reference market calendars

The supported-symbol registry SHALL allow each symbol to reference a persisted market calendar when
a verified mapping exists.

#### Scenario: Registry calendar column is migrated

- **WHEN** the database is upgraded through this change
- **THEN** `supported_symbols` has a nullable `calendar_code` column
- **AND** non-null `calendar_code` values reference `market_calendars.code`

#### Scenario: Obvious calendar mappings are seeded

- **WHEN** the migration runs against a database containing current supported symbol rows
- **THEN** Forex pairs and spot `XAU/USD` can reference the Forex calendar
- **AND** US stocks, ETFs, and stock indexes can reference the US regular-market calendar
- **AND** crypto symbols and unverified futures proxy symbols can remain unmapped

#### Scenario: Public symbol response remains unchanged

- **WHEN** a client sends `GET /v1/symbols` after this migration
- **THEN** the response uses the existing supported-symbol response shape
- **AND** it does not expose `calendar_code`
