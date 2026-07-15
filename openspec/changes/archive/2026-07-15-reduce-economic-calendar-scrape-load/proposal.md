## Why

The economic calendar cronjob currently performs extended scraping for every event every five
minutes, creating enough upstream traffic to trigger HTTP 403 blocking. The gateway needs to keep
base values fresh while fetching stable description and news metadata only when needed.

## What Changes

- Keep `ECONOMIC_CALENDAR_POLL_SECONDS` unchanged; production continues polling every `300` seconds
  during and after rollout.
- Fetch regular base calendar data with `extended=False` at the configured polling interval
  (`300` seconds in production).
- Fetch description and news URL details only for new events or events still missing either field,
  and attempt enrichment for an event at most once per UTC day.
- Preserve existing `description` and `news_url` values when a base refresh supplies `NULL`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `economic-calendar-refresh-cronjob`: Separate frequent base refreshes from throttled per-event
  enrichment instead of requesting extended details for the full window on every run.
- `economic-calendar-persistence`: Preserve stored enrichment during base upserts and track the last
  enrichment attempt needed to enforce the daily limit.

## Impact

- Affected provider adapter: `app/providers/market_calendar_tool.py`.
- Affected refresh service: `app/services/economic_calendar_refresh.py`.
- Affected persistence: economic calendar repository, model, and one database migration for an
  internal enrichment-attempt timestamp.
- Affected documentation: describe the reduced-load refresh behavior without changing the existing
  `300` second production interval.
- Public `/v1/economic-calendar` request and response contracts remain unchanged.
- No new dependency is required.
