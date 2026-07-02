## Why

MDG needs a local persistence layer for economic calendar entries before REST/WS consumers can safely move away from WS-owned crawling. Persisting entries makes reads fast and lets later refresh logic upsert `actual`, `forecast`, and revision changes without scraping on every request.

## What Changes

- Add database persistence for normalized economic calendar events from `market-calendar-tool`.
- Store one row per upstream event identity and calendar type.
- Keep value fields such as `actual`, `forecast`, `previous`, and `revision` as text.
- Add indexes for range queries by scheduled time, calendar type, and currency.
- Add SQLAlchemy model matching the database schema.
- Do not add provider fetch logic, cronjob refresh logic, REST endpoints, WebSocket fanout, or public API contracts in this change.

## Capabilities

### New Capabilities
- `economic-calendar-persistence`: Database schema and model contract for persisted economic calendar events.

### Modified Capabilities
- None.

## Impact

- Affected code: Alembic migration, SQLAlchemy model, and focused persistence tests.
- Affected systems: PostgreSQL schema.
- Public APIs: none.
- Dependencies: none.
