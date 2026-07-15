## Context

The current five-minute refresh calls `market-calendar-tool` with `extended=True`. For the current
nine-day window this performs four base requests plus one detail request per event on every run,
which can exceed 90,000 upstream requests per day and has resulted in HTTP 403 responses.

The package's public API only supports all-or-nothing extended scraping. It cannot request details
for a selected set of event IDs. Existing persisted rows already provide the identity and nullable
enrichment fields needed to select only new or incomplete events.

## Goals / Non-Goals

**Goals:**

- Keep base calendar values on the existing five-minute production cadence.
- Request detail data only for new or incomplete events.
- Enforce at most one detail attempt per event per UTC day across process restarts.
- Preserve previously stored enrichment when a base refresh has no enrichment values.
- Keep the existing polling interval and cronjob registration unchanged during rollout.

**Non-Goals:**

- Do not add retries, proxy support, browser impersonation, or Cloudflare bypass logic.
- Do not change the public economic calendar API.
- Do not crawl news articles or restore history persistence.
- Do not add a second cronjob or a new enrichment interval setting.

## Decisions

- Use one refresh flow with two phases.
  1. Fetch and persist base events for all supported types with `extended=False`.
  2. Select persisted events needing enrichment, mark their attempt, fetch only their details, and
     persist any non-null enrichment returned.
  - Alternative considered: a second daily cronjob. Rejected because the existing poll can cheaply
    check eligibility and immediately enrich newly discovered events without another scheduler or
    setting.

- Add nullable `enrichment_attempted_at` as an internal timezone-aware database timestamp.
  - An event is eligible when `description` or `news_url` is null and its attempt timestamp is null
    or earlier than the current UTC day.
  - Mark selected events before network calls so failures and empty detail responses are not retried
    every five minutes.
  - Alternative considered: an in-memory daily marker. Rejected because restart would lose the
    throttle and could repeat the blocked request burst.

- Keep `market-calendar-tool` for base scraping with `extended=False`, and issue selected detail
  GETs from the gateway adapter using already-installed `aiohttp`.
  - Detail URLs use the upstream `/details/{site-number}-{event-id}` endpoint already used by the
    package, with concurrency capped at the package's existing default of five.
  - Normalize `data.specs` and `data.linked_threads.news` through the existing gateway description
    and news URL parsers.
  - Direct protocol access is necessary because the package has no public selected-ID detail API;
    using `extended=True` would reintroduce one request for every event on every base refresh.

- Preserve enrichment in base upserts.
  - An incoming null `description` or `news_url` keeps the persisted value and does not count as a
    content change.
  - A non-null enrichment response can insert or replace the corresponding persisted value and
    participates in existing `last_changed_at` handling.

- Isolate detail failures per event.
  - A failed or malformed detail response is logged, leaves enrichment unchanged, and remains
    ineligible until the next UTC day because the attempt was already recorded.
  - Base scrape failure keeps the existing behavior of failing the cronjob run.

## Risks / Trade-offs

- [An event legitimately has no news URL or description] -> it is retried once per UTC day while it
  remains in the refresh window, never every five minutes.
- [The private upstream detail URL or JSON shape changes] -> keep the direct call and parsing inside
  the provider adapter with focused fixture tests.
- [Marking an attempt before fetching delays recovery from a transient detail error] -> accept a
  one-day delay to guarantee the upstream cannot be hammered.
- [The server IP remains blocked after request volume drops] -> address proxy/routing in a separate
  change based on production response evidence; this change does not alter the polling cadence.

## Migration Plan

1. Deploy the nullable `enrichment_attempted_at` migration and application changes without changing
   `ECONOMIC_CALENDAR_POLL_SECONDS`.
2. Restart the gateway with the existing `300` second production interval.
3. Verify base refresh success, daily enrichment attempt counts, and absence of repeated HTTP 403
   responses.
4. Roll back to the previous image if needed; the added nullable column can remain.

## Open Questions

None.
