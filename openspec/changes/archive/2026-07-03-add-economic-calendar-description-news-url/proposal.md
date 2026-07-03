## Why

Economic calendar consumers need enough context to understand an event and optionally crawl the
related article themselves. `market-calendar-tool` already supports extended event details, so the
gateway can persist and expose only the useful additions without owning news crawling.

## What Changes

- Fetch extended economic calendar details through `market-calendar-tool`.
- Persist nullable `description` and `news_url` fields on `economic_calendar_events`.
- Return `description` and `newsUrl` from `GET /v1/economic-calendar`.
- Parse only the first usable related-news `/hit` URL for each event and leave full news crawling to
  downstream consumers.
- Do not persist historical event rows, raw news HTML, news text, or JSON payloads.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `economic-calendar-api`: expose `description` and `newsUrl` on economic calendar events.
- `economic-calendar-persistence`: store nullable description and news URL fields.
- `economic-calendar-refresh-cronjob`: enrich persisted rows from `market-calendar-tool` extended details.

## Impact

- Affected provider adapter: `app/providers/market_calendar_tool.py`.
- Affected domain/persistence/API DTOs: economic calendar event models and serializers.
- Affected database: one Alembic migration adding nullable `description` and `news_url`.
- Affected tests/docs: economic calendar provider, repository, API, persistence, and contract docs.
- No new dependency, no full news crawling, no history persistence, and no JSONB fields.
