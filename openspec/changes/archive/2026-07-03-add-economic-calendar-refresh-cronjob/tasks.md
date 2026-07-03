## 1. Dependency And Config

- [x] 1.1 Add `market-calendar-tool` to project dependencies and lockfile.
- [x] 1.2 Add `economic_calendar_poll_seconds` setting with default `300` and minimum `0`.

## 2. Provider Adapter And Normalization

- [x] 2.1 Add `app/providers/market_calendar_tool.py` behind a gateway-owned adapter.
- [x] 2.2 Map `FOREX`, `METALS`, `ENERGY`, and `CRYPTO` to the matching upstream library sites.
- [x] 2.3 Run blocking scrape calls outside the event loop.
- [x] 2.4 Normalize scraped rows into economic calendar domain events with `actual`, `forecast`,
  `previous`, `revision`, and better/worse fields preserved as strings or null.

## 3. Refresh Persistence

- [x] 3.1 Add repository support for upserting economic calendar events by
  `(calendar_type, external_event_id)`.
- [x] 3.2 Preserve `first_seen_at`, always update `last_seen_at`, and update `last_changed_at` only
  when normalized event content changes.
- [x] 3.3 Keep `/v1/economic-calendar` read-only with no scrape fallback.

## 4. Cronjob Wiring

- [x] 4.1 Add `EconomicCalendarFetchCronjob` using the existing `Cronjob` base.
- [x] 4.2 Refresh the fixed V1 window: 2 days lookback, 7 days lookahead, all four calendar types.
- [x] 4.3 Register the cronjob in FastAPI lifespan only when database access exists and
  `ECONOMIC_CALENDAR_POLL_SECONDS > 0`.
- [x] 4.4 Configure the cronjob to run on startup and then by interval.

## 5. Tests

- [x] 5.1 Add unit tests for provider type mapping and row normalization.
- [x] 5.2 Add unit tests for refresh service date window and provider/repository calls.
- [x] 5.3 Add unit tests for lifespan registration enabled, disabled, and no-database paths.
- [x] 5.4 Add integration coverage for repository upsert timestamp behavior when PostgreSQL is
  configured.

## 6. Validation

- [x] 6.1 Run focused economic calendar refresh tests.
- [x] 6.2 Run `uv run ruff check app tests`.
- [x] 6.3 Run `uv run mypy app`.
