## Why

The gateway now has a database place to store market calendars, but it only seeds the two obvious
calendar types. We need the remaining supported asset universe mapped to explicit calendar types
before a later change generates sessions or filters candles from persisted calendar data.

## What Changes

- Add the `pandas-market-calendars` dependency as the approved local calendar source.
- Seed reusable calendar type definitions for all currently supported MDG asset groups.
- Expand symbol `calendar_code` mappings for supported assets where the provider/proxy calendar is
  clear enough to encode.
- Keep calendar session generation, refresh jobs, provider data comparison, and candle filtering out
  of scope.

## Capabilities

### New Capabilities

- `market-calendar-type-seeding`: Dependency and seed data for supported market calendar types and
  symbol-to-calendar mappings.

### Modified Capabilities

- None.

## Impact

- Affected code: dependency lock files, Alembic seed migration, and focused migration tests.
- Affected data: `market_calendars` rows and `supported_symbols.calendar_code` values.
- Public APIs: none.
- Runtime behavior: none; no request path reads the new calendar data in this change.
