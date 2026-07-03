## Why

MDG can now store and serve economic calendar events, but the table still needs a process-owned
refresh path. A small in-process cronjob lets MDG fetch calendar entries with `market-calendar-tool`
and keep the existing `/v1/economic-calendar` API backed by local PostgreSQL data.

## What Changes

- Add `market-calendar-tool` as the economic calendar scraping dependency.
- Add a provider adapter that calls `market-calendar-tool` for `FOREX`, `METALS`, `ENERGY`, and
  `CRYPTO`.
- Add an economic calendar refresh service that normalizes scraped rows and upserts them into
  `economic_calendar_events`.
- Add an `EconomicCalendarFetchCronjob` registered through the existing `CronjobManager`.
- Add only one runtime setting: `ECONOMIC_CALENDAR_POLL_SECONDS`.
- Treat `ECONOMIC_CALENDAR_POLL_SECONDS=0` as disabled; any positive value registers the cronjob.
- Use fixed V1 defaults in code: look back 2 days, look ahead 7 days, all four calendar types,
  run on startup, and non-extended scrape.
- Do not add WebSocket fanout, in-memory calendar cache, admin run endpoint, distributed locks, or
  database schema changes in this change.

## Capabilities

### New Capabilities

- `economic-calendar-refresh-cronjob`: Periodically fetch and persist economic calendar events
  using the in-process cronjob core.

### Modified Capabilities

- None.

## Impact

- Affected code: settings, FastAPI lifespan cronjob registration, economic calendar provider
  adapter, refresh service, repository upsert method, and focused tests.
- Affected systems: outbound HTTP scraping through `market-calendar-tool`; PostgreSQL upserts into
  `economic_calendar_events`.
- Public APIs: none.
- Dependencies: add `market-calendar-tool`.
- Migrations: none.
