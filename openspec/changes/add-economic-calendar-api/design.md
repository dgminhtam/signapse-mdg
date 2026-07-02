## Context

`economic_calendar_events` already stores normalized calendar rows with public `calendar_type`, upstream `external_event_id`, scheduled time, values, and lifecycle timestamps. The next step is a read-only API so consumers can load persisted calendar entries from MDG without calling upstream economic-calendar sites.

Existing HTTP routes keep DTOs in route modules, parse request input in services, read PostgreSQL through repositories, serialize datetimes as ISO-8601 UTC strings, and use request-specific domain errors mapped to the shared `{error:{code,message,details}}` shape.

## Goals / Non-Goals

**Goals:**
- Add `GET /v1/economic-calendar`.
- Read only from `economic_calendar_events`.
- Validate UTC `from`/`to` as a half-open range: `from <= scheduled_at < to`.
- Support optional CSV filters for `types`, `currencies`, and `impact`.
- Support optional `limit` with a configured or local default and max.
- Return public event `key` as `{type}:{external_event_id}`.
- Return `type`, not source/provider/site.
- Return `events: []` for valid empty ranges.

**Non-Goals:**
- No provider scraping or `market-calendar-tool` adapter.
- No on-demand refresh when the database is empty.
- No cronjob wiring.
- No WebSocket endpoint or fanout.
- No cache.
- No database migration.

## Decisions

### Read from PostgreSQL only

The API will query persisted events and never call upstream scraping logic. If the table has no rows for a valid range, the response is successful with an empty `events` array.

Alternative considered: scrape on cache miss. Rejected because it would make API latency and availability depend on third-party calendar sites and blur this API with refresh behavior.

### Use `key` for public event identity

The response will expose `key`, not `id`. `key` is `{type}:{external_event_id}` and is stable enough for client dedupe/update. The internal DB primary key remains hidden.

Alternative considered: expose `id`. Rejected because clients can confuse it with the database primary key.

Alternative considered: expose `code`. Rejected because this repo already uses `code` heavily for errors and enum-like values.

### Keep filters simple CSV values

`types`, `currencies`, and `impact` follow the existing quote style of comma-separated query values. Values are trimmed, empty values are removed, and duplicates are collapsed in request order.

Alternative considered: repeated query params. Rejected for V1 because current MDG list filters already use CSV.

### Validate only stable app-owned enums

`types` are restricted to `FOREX`, `METALS`, `ENERGY`, and `CRYPTO`. `currencies` and `impact` are validated only as non-empty bounded strings because upstream labels can vary.

Alternative considered: strict impact enum. Rejected until the market-calendar-tool adapter normalizes impact values consistently.

### Keep implementation shape boring

Add:
- `app/domain/economic_calendar.py` for request/result dataclasses and repository protocol.
- `app/services/economic_calendar.py` for parsing and service orchestration.
- `PostgresEconomicCalendarRepository` in `app/db/repositories.py`.
- `app/api/routes_economic_calendar.py` for FastAPI DTOs and dependency wiring.
- an `EconomicCalendarRequestError` handler.

Alternative considered: put everything in the route file. Rejected because existing non-trivial routes keep parsing/service/repository boundaries separate.

## Risks / Trade-offs

- No refresh fallback means empty responses can reflect stale or missing refresh jobs -> acceptable for V1; refresh/cron work owns freshness later.
- No `changedSince` makes polling less efficient -> add only when WS/incremental clients require it.
- `key` contains type and external ID -> document it as stable identity, not a provider/source contract.
- Impact filter may be case-sensitive if stored labels vary -> normalize query values to uppercase and compare stored impact exactly first; adapter normalization can improve this later.
