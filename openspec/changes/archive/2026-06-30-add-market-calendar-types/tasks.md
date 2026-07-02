## 1. Dependency

- [x] 1.1 Add a pinned `pandas-market-calendars` dependency using `uv`.
- [x] 1.2 Add a minimal dependency-boundary test that imports `pandas_market_calendars`.

## 2. Calendar Type Seed

- [x] 2.1 Add an Alembic seed migration after the market calendar table migration.
- [x] 2.2 Upsert `CRYPTO_24_7`, `FOREX_24_5`, `US_REGULAR`, `CME_ENERGY`, `CME_METALS`, `CME_AGRICULTURE`, and `ICE_SOFTS`.
- [x] 2.3 Update current supported symbols to the intended `calendar_code` values.
- [x] 2.4 Keep `market_calendar_sessions` empty in this change.

## 3. Verification

- [x] 3.1 Add focused migration tests for seeded calendar types and symbol mappings.
- [x] 3.2 Run the focused tests plus `uv run pytest`.
- [x] 3.3 Run `uv run ruff check .`, `uv run mypy app`, and `openspec.cmd validate add-market-calendar-types --strict`.
