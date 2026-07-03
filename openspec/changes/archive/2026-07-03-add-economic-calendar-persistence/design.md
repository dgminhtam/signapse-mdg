## Context

`market-calendar-tool` can produce normalized base economic calendar rows for ForexFactory, MetalsMine, EnergyExch, and CryptoCraft. MDG needs a local table for these rows before later work adds fetch, cron refresh, REST, or WebSocket delivery.

The current repository style uses PostgreSQL, Alembic migrations, SQLAlchemy models, `Text` fields for app-owned enum values, explicit unique constraints, and query indexes.

## Goals / Non-Goals

**Goals:**
- Add one table, `economic_calendar_events`, for normalized base calendar events.
- Store one row per `(calendar_type, external_event_id)`.
- Preserve `actual`, `forecast`, `previous`, and `revision` exactly as text.
- Track first seen, last seen, last changed, created, and updated timestamps.
- Add indexes for the expected read paths: time range, type+time range, and currency+time range.
- Add a SQLAlchemy model that mirrors the table.

**Non-Goals:**
- No fetch logic, cronjob, cache, API endpoint, WebSocket fanout, or repository service.
- No persistence for `market-calendar-tool` extended `specs`, `history`, or `news`.
- No raw payload table.
- No refresh run history table.

## Decisions

### Use a single event table

Create only `economic_calendar_events`. V1 reads need the base calendar event list, not normalized child records.

Alternative considered: split values, revisions, and event metadata into separate tables. Rejected because `market-calendar-tool` base rows already provide the complete list view, and separate tables do not buy anything until detailed event history is exposed.

### Use public calendar type as the partition key

Use `calendar_type` with values `FOREX`, `METALS`, `ENERGY`, and `CRYPTO`. Do not store or expose provider site names in the schema.

Alternative considered: store upstream source/site. Rejected for V1 because the external contract only needs the calendar type, and the type is enough to dedupe IDs across upstream calendars.

### Keep event values as text

Store `actual`, `forecast`, `previous`, `revision`, `actual_better_worse`, and `revision_better_worse` as nullable text. Economic calendar values can contain suffixes, percentages, words, or missing values.

Alternative considered: numeric columns. Rejected because parsing would lose original provider text and introduce logic outside this schema change.

### Constrain only stable app-owned values

Add a check constraint for `calendar_type`. Do not constrain `impact` or better/worse text until the provider adapter proves stable normalized values.

Alternative considered: strict database enum/checks for all categorical fields. Rejected because upstream label drift should not break persistence.

### Use minimal indexes

Add:
- `ix_economic_calendar_events_scheduled_at` on `scheduled_at`
- `ix_economic_calendar_events_type_scheduled_at` on `(calendar_type, scheduled_at)`
- `ix_economic_calendar_events_currency_scheduled_at` on `(currency, scheduled_at)`

Alternative considered: add indexes for impact and last_changed immediately. Rejected until REST/WS query patterns prove they need them.

## Risks / Trade-offs

- Upstream event IDs may not be globally unique -> include `calendar_type` in the unique identity.
- Provider labels may drift -> keep mutable categorical fields as text.
- No raw payload can make scraper drift harder to debug -> add `raw_payload jsonb` only if real provider changes require it.
- No refresh run table means less operational history -> use `max(last_seen_at)` for basic freshness; add run history only when operations need it.

## Migration Plan

1. Add Alembic migration creating `economic_calendar_events`, constraints, and indexes.
2. Add SQLAlchemy model in `app/db/models.py`.
3. Add focused migration/model tests.
4. Rollback drops indexes and the table.
