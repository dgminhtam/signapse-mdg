## 1. Schema

- [x] 1.1 Add an Alembic migration for `market_calendars`, `market_calendar_sessions`, and nullable `supported_symbols.calendar_code`.
- [x] 1.2 Add foreign keys, uniqueness, time-order checks, and a calendar/time lookup index.
- [x] 1.3 Seed only calendar definition rows and obvious existing symbol calendar mappings.

## 2. Models

- [x] 2.1 Add SQLAlchemy models for the new calendar tables.
- [x] 2.2 Add `calendar_code` to the supported-symbol model without changing public DTOs.

## 3. Verification

- [x] 3.1 Add focused migration/model tests for constraints and seeded mappings.
- [x] 3.2 Run `uv run pytest` for the focused database tests available in this repo.
- [x] 3.3 Run `openspec.cmd validate add-market-calendar-tables --strict`.
