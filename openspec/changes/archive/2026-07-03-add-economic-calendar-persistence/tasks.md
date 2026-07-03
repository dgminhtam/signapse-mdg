## 1. Migration

- [x] 1.1 Add an Alembic migration creating `economic_calendar_events`.
- [x] 1.2 Add columns for event identity, display fields, value fields, and lifecycle timestamps.
- [x] 1.3 Add `uq_economic_calendar_events_identity` on `(calendar_type, external_event_id)`.
- [x] 1.4 Add a `calendar_type` check constraint for `FOREX`, `METALS`, `ENERGY`, and `CRYPTO`.
- [x] 1.5 Add indexes on `scheduled_at`, `(calendar_type, scheduled_at)`, and `(currency, scheduled_at)`.
- [x] 1.6 Add downgrade logic that drops indexes and the table.

## 2. Model

- [x] 2.1 Add `EconomicCalendarEventModel` to `app/db/models.py`.
- [x] 2.2 Mirror migration column nullability, timestamp defaults, unique constraint, check constraint, and indexes in the model.

## 3. Tests

- [x] 3.1 Add migration/schema tests that verify table columns, constraints, and indexes.
- [x] 3.2 Add model tests that verify SQLAlchemy metadata maps to `economic_calendar_events`.
- [x] 3.3 Verify duplicate `(calendar_type, external_event_id)` rows are rejected.
- [x] 3.4 Verify unsupported `calendar_type` values are rejected.
- [x] 3.5 Verify no economic calendar provider, cronjob, REST, or WebSocket behavior is added.

## 4. Validation

- [x] 4.1 Run the focused economic calendar persistence tests.
- [x] 4.2 Run `uv run ruff check app tests alembic`.
- [x] 4.3 Run `uv run mypy app`.
