## Why

The gateway's market-session rules are currently code-only, which makes future exchange-calendar
updates hard to audit or seed ahead of time. A small database foundation lets the project persist
calendar sessions before later candle logic starts reading them.

## What Changes

- Add PostgreSQL schema for reusable market calendar definitions and generated trading sessions.
- Add an optional calendar mapping on enabled symbols so multiple assets can share one calendar.
- Seed only the obvious initial mappings: crypto stays always-open, Forex/spot metals use the
  Forex calendar, and US equities/ETFs/indexes use the US regular-market calendar.
- Keep candle filtering, provider routing, pandas-market-calendars generation, and public API
  behavior out of scope for this change.

## Capabilities

### New Capabilities
- `market-calendar-persistence`: Database persistence for market calendar definitions, generated
  trading sessions, and symbol-to-calendar mapping.

### Modified Capabilities
- `supported-symbol-registry`: Enabled symbols can store an optional calendar mapping for later
  market-session logic.

## Impact

- Affected code: Alembic migration, SQLAlchemy models, symbol seed/update migration data, and
  focused database tests if existing migration coverage allows.
- Affected systems: PostgreSQL schema for calendar metadata and sessions.
- Public APIs: none.
- Dependencies: none in this change; pandas-market-calendars generation is deferred.
