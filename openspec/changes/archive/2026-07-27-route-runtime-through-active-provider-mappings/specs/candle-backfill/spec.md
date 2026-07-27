## MODIFIED Requirements

### Requirement: Backfill scope uses the enabled symbol registry

The backfill command SHALL select symbols from the PostgreSQL-backed enabled symbol registry and
MUST route provider filtering, persisted-candle reads, and provider fills through each symbol's
single active normalized provider mapping. It MUST NOT use an inactive mapping or legacy provider
column.

#### Scenario: Backfill runs without explicit symbol filters

- **WHEN** the command is run for all enabled symbols
- **THEN** it considers enabled registry rows with active mappings as the backfill universe
- **AND** disabled or absent symbols are not processed

#### Scenario: Backfill runs with explicit symbol filters

- **WHEN** the command is run with a subset of canonical symbols
- **THEN** it processes only matching enabled registry rows resolved through their active mappings
- **AND** it rejects unknown or disabled symbols before provider access

#### Scenario: Backfill filters by provider

- **WHEN** the command includes a provider filter
- **THEN** it compares that filter with each symbol's active normalized provider
- **AND** inactive provider mappings do not add the symbol to the backfill scope

#### Scenario: Enabled backfill symbol lacks an active mapping

- **WHEN** an enabled symbol selected for backfill has no active normalized mapping
- **THEN** the command fails through the sanitized database-unavailable boundary
- **AND** no provider fill is attempted for that symbol
