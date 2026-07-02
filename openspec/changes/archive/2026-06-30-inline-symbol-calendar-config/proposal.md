## Why

`pandas_market_calendars` provides local calendar rules, so persisting generated market sessions is unnecessary for the current runtime-filtering goal. The simpler schema is to keep each supported symbol's calendar source metadata inline with the symbol registry.

## What Changes

- Remove `market_calendars` and `market_calendar_sessions` from the intended schema.
- Replace `supported_symbols.calendar_code` with inline calendar config columns:
  - `calendar_source`
  - `calendar_name`
  - `calendar_timezone`
- Seed calendar config directly onto currently supported symbols.
- Keep public symbol API response shape unchanged.
- Do not add candle filtering, calendar generation, CLI refresh, scheduler, or background jobs in this change.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `supported-symbol-registry`: store nullable inline market-calendar config on supported symbols.
- `market-calendar-persistence`: retire materialized calendar definition/session persistence requirements for this direction.
- `market-calendar-type-seeding`: replace reusable calendar type rows and symbol `calendar_code` mappings with inline supported-symbol config seeding.

## Impact

- Affected database schema: `supported_symbols`, removal of `market_calendars`, removal of `market_calendar_sessions`.
- Affected models/tests: SQLAlchemy symbol model and registry schema tests.
- Affected migrations: new migration to drop old calendar tables/foreign key/column and add inline config columns.
- No public API contract change.
- No runtime market-data behavior change.
