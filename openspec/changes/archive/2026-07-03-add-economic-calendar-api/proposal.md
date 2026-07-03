## Why

MDG now has a persisted `economic_calendar_events` table, but clients still need a stable API contract to read those entries without knowing provider/source details. A read-only `/v1/economic-calendar` endpoint lets WS and other consumers switch to MDG as the calendar source before refresh logic is added.

## What Changes

- Add `GET /v1/economic-calendar` as a read-only REST API backed by `economic_calendar_events`.
- Support UTC half-open time range filtering with `from` inclusive and `to` exclusive.
- Support optional filters for `types`, `currencies`, `impact`, and `limit`.
- Return public event identity as `key`, not DB `id`.
- Return public calendar `type` values without exposing upstream provider/source names.
- Keep event value fields as strings or null.
- Do not add provider scraping, cronjob refresh, cache, WebSocket streaming, or database schema changes in this change.

## Capabilities

### New Capabilities
- `economic-calendar-api`: Read-only HTTP API for loading persisted economic calendar events.

### Modified Capabilities
- None.

## Impact

- Affected code: new route module, domain/service parsing, repository read method, error handling, app router wiring, focused API tests.
- Affected systems: PostgreSQL reads from `economic_calendar_events`.
- Public APIs: new `GET /v1/economic-calendar`.
- Dependencies and migrations: none.
