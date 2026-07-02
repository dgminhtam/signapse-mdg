## Context

The repository now has three pieces this change can reuse:

- `app/core/cronjob.py` provides an in-process async `CronjobManager`.
- `economic_calendar_events` persists normalized calendar entries.
- `GET /v1/economic-calendar` reads persisted rows and never scrapes upstream sources.

`market-calendar-tool` provides one-shot scraping for ForexFactory, MetalsMine, EnergyExch, and
CryptoCraft. It does not provide a daemon, durable queue, or database persistence, so MDG owns the
refresh loop.

## Goals / Non-Goals

**Goals:**

- Fetch `FOREX`, `METALS`, `ENERGY`, and `CRYPTO` economic calendar rows.
- Persist scraped rows into `economic_calendar_events`.
- Use the existing in-process `CronjobManager`.
- Keep runtime configuration to `ECONOMIC_CALENDAR_POLL_SECONDS` only.
- Refresh a small fixed window: 2 days lookback and 7 days lookahead.
- Run once on startup when enabled so an empty DB can fill without waiting for the first interval.
- Preserve `first_seen_at`, update `last_seen_at`, and update `last_changed_at` only when event
  content changes.

**Non-Goals:**

- No WebSocket fanout.
- No in-memory economic calendar cache.
- No admin API to trigger refresh.
- No distributed lock or exactly-once behavior across workers.
- No database migration.
- No configurable calendar type list, lookback/lookahead days, run-on-start flag, or extended scrape
  flag in V1.

## Decisions

### Use one setting as both interval and enable flag

Add `economic_calendar_poll_seconds` with env name `ECONOMIC_CALENDAR_POLL_SECONDS`.

- `0` disables registration.
- `> 0` registers `EconomicCalendarFetchCronjob`.
- Default should be `300`.

Alternative considered: separate `ECONOMIC_CALENDAR_ENABLED`. Rejected because `0` is enough and
keeps operations simple.

### Keep fixed V1 refresh scope

The job fetches:

- calendar types: `FOREX`, `METALS`, `ENERGY`, `CRYPTO`
- lookback: 2 days
- lookahead: 7 days
- `run_on_start=True`
- `extended=False`

Alternative considered: expose all values as settings. Rejected until there is a real operational
need to tune them independently.

### Hide `market-calendar-tool` behind an adapter

Add `app/providers/market_calendar_tool.py` to map public calendar types to upstream `Site` values
and normalize third-party exceptions into gateway-owned errors.

The adapter should run blocking scrape work via `asyncio.to_thread(...)` so FastAPI's event loop is
not blocked by requests, parsing, or pandas work.

Alternative considered: call the library directly from the cronjob. Rejected because provider
internals would leak into service/cronjob code.

### Upsert by persisted calendar identity

The repository upsert uses the existing unique identity:

```text
(calendar_type, external_event_id)
```

On conflict:

- keep existing `first_seen_at`
- update `last_seen_at`
- update `updated_at`
- update event fields from the latest scrape
- set `last_changed_at` only when stored event content differs from incoming content

Alternative considered: delete and reinsert every refresh. Rejected because it loses lifecycle
timestamps and creates noisier changes for clients.

### Keep refresh independent from read API

The existing `/v1/economic-calendar` endpoint remains read-only from PostgreSQL. It does not call
the refresh service on empty results.

Alternative considered: scrape on API miss. Rejected because it couples user-facing latency to
third-party calendar site availability.

## Risks / Trade-offs

- Multi-worker duplicate refreshes -> accepted for V1; DB upsert keeps rows stable. Add a Postgres
  advisory lock only if MDG runs multiple workers/replicas and duplicate scraping becomes a problem.
- Upstream HTML/parser changes -> cronjob failure is isolated by `CronjobManager`; existing API keeps
  serving last persisted rows.
- Fixed lookback/lookahead may not fit all operations -> add settings later if production evidence
  says the defaults are wrong.
- Python/package compatibility with Python 3.14 -> verify `uv sync`, import, and focused provider
  tests during implementation.
