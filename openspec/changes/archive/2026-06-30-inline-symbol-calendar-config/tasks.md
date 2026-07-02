## 1. Schema Migration

- [x] 1.1 Add an Alembic migration that drops the `supported_symbols.calendar_code` foreign key and column.
- [x] 1.2 Drop `market_calendar_sessions` and `market_calendars`.
- [x] 1.3 Add nullable `calendar_source`, `calendar_name`, and `calendar_timezone` columns to `supported_symbols`.
- [x] 1.4 Seed inline calendar config values for all currently supported symbols.
- [x] 1.5 Provide a downgrade that restores the previous calendar tables and `calendar_code` shape.

## 2. Models And Tests

- [x] 2.1 Update `SupportedSymbolModel` with the inline calendar config columns.
- [x] 2.2 Remove unused calendar table models.
- [x] 2.3 Update registry schema tests for the new columns and removed tables.
- [x] 2.4 Update seed idempotency tests to assert inline calendar config values.
- [x] 2.5 Keep public symbol DTO tests unchanged except for confirming calendar config is not exposed.

## 3. Verification

- [x] 3.1 Run `openspec.cmd validate inline-symbol-calendar-config --strict`.
- [x] 3.2 Run `uv run pytest`.
- [x] 3.3 Run `uv run ruff check .`.
- [x] 3.4 Run `uv run mypy app`.
