## 1. Domain And Service

- [x] 1.1 Add economic calendar domain dataclasses and repository protocol.
- [x] 1.2 Add `EconomicCalendarRequestError` and map it to the shared HTTP error shape.
- [x] 1.3 Implement request parsing for UTC `from`/`to`, CSV `types`, `currencies`, `impact`, and `limit`.
- [x] 1.4 Implement read-only service orchestration with no provider/scrape fallback.

## 2. Persistence Read

- [x] 2.1 Add `PostgresEconomicCalendarRepository` that reads `EconomicCalendarEventModel`.
- [x] 2.2 Filter by half-open scheduled range and optional `types`, `currencies`, and `impact`.
- [x] 2.3 Order rows by `scheduled_at`, `calendar_type`, and `external_event_id`.
- [x] 2.4 Apply request limit at the database query.

## 3. HTTP API

- [x] 3.1 Add `app/api/routes_economic_calendar.py` with DTOs and dependency wiring.
- [x] 3.2 Return `key` as `{type}:{external_event_id}` and hide DB `id` and upstream source fields.
- [x] 3.3 Register the route and error handler in `app/main.py`.

## 4. Tests

- [x] 4.1 Add unit tests for parser validation and normalized filters.
- [x] 4.2 Add unit tests for service returning empty lists without provider/scrape fallback.
- [x] 4.3 Add API tests for success response shape, filters, ordering, and request errors.
- [x] 4.4 Add integration coverage for repository range/filter/limit queries when PostgreSQL is configured.

## 5. Validation

- [x] 5.1 Run focused economic calendar API tests.
- [x] 5.2 Run `uv run ruff check app tests`.
- [x] 5.3 Run `uv run mypy app`.
