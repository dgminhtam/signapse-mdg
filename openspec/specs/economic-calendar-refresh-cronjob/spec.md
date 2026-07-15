## Purpose

Defines the scheduled economic calendar refresh flow, provider normalization, persistence, and failure isolation.

## Requirements

### Requirement: Economic calendar refresh cronjob registration
The gateway SHALL register an in-process economic calendar refresh cronjob when calendar polling is
enabled and database access is configured.

#### Scenario: Register cronjob when polling is enabled
- **WHEN** `DATABASE_URL` is configured
- **AND** `ECONOMIC_CALENDAR_POLL_SECONDS` is greater than zero
- **THEN** the gateway registers an economic calendar refresh cronjob with the existing
  `CronjobManager`
- **AND** the cronjob interval equals `ECONOMIC_CALENDAR_POLL_SECONDS`

#### Scenario: Disable cronjob with zero polling interval
- **WHEN** `ECONOMIC_CALENDAR_POLL_SECONDS` is `0`
- **THEN** the gateway does not register the economic calendar refresh cronjob

#### Scenario: Skip cronjob without database
- **WHEN** `DATABASE_URL` is not configured
- **THEN** the gateway does not register the economic calendar refresh cronjob

### Requirement: Economic calendar refresh scope
The economic calendar refresh cronjob SHALL fetch a fixed V1 calendar window and calendar type set.

#### Scenario: Refresh fixed date window
- **WHEN** the refresh cronjob runs
- **THEN** it fetches events from 2 days before the current UTC day through 7 days after the current
  UTC day

#### Scenario: Refresh supported calendar types
- **WHEN** the refresh cronjob runs
- **THEN** it fetches `FOREX`, `METALS`, `ENERGY`, and `CRYPTO` calendar events

#### Scenario: Run refresh on startup
- **WHEN** the cronjob is registered and `CronjobManager.start()` is called
- **THEN** the economic calendar refresh cronjob runs once on startup before waiting for the first
  interval tick

### Requirement: Economic calendar refresh separates base and detail requests

The economic calendar refresh SHALL fetch base values without extended detail retrieval and SHALL
request event details only for persisted enrichment candidates.

#### Scenario: Regular refresh fetches base data only
- **WHEN** the economic calendar refresh runs
- **THEN** the provider adapter calls `market-calendar-tool` with `extended=False` for each
  supported calendar type
- **AND** it does not use the package's full-window extended scrape

#### Scenario: Five-minute production polling remains supported
- **WHEN** `ECONOMIC_CALENDAR_POLL_SECONDS` is configured as `300`
- **THEN** the base refresh runs at the existing five-minute interval
- **AND** detail eligibility is evaluated after the fetched base events are persisted

### Requirement: Economic calendar provider adapter
The gateway SHALL access `market-calendar-tool` only through a gateway-owned provider adapter.

#### Scenario: Map public types to upstream sites
- **WHEN** the refresh service requests events for public calendar types
- **THEN** the provider adapter maps `FOREX`, `METALS`, `ENERGY`, and `CRYPTO` to the corresponding
  `market-calendar-tool` upstream sites

#### Scenario: Do not block the event loop
- **WHEN** the provider adapter calls `market-calendar-tool`
- **THEN** blocking scrape work runs outside the FastAPI event loop

### Requirement: Economic calendar refresh persistence
The economic calendar refresh cronjob SHALL persist fetched events by upserting normalized rows into
`economic_calendar_events`.

#### Scenario: Insert new event
- **WHEN** a fetched event has no existing row with the same `calendar_type` and `external_event_id`
- **THEN** the gateway inserts a new row into `economic_calendar_events`
- **AND** sets `first_seen_at`, `last_seen_at`, and `last_changed_at`

#### Scenario: Update seen event without content change
- **WHEN** a fetched event matches an existing row
- **AND** the normalized event content has not changed
- **THEN** the gateway updates `last_seen_at`
- **AND** preserves `first_seen_at`
- **AND** preserves `last_changed_at`

#### Scenario: Update changed event
- **WHEN** a fetched event matches an existing row
- **AND** any normalized event content field has changed
- **THEN** the gateway updates the stored event fields
- **AND** updates `last_seen_at`
- **AND** updates `last_changed_at`

### Requirement: Economic calendar detail requests are candidate-scoped

The refresh service SHALL request description and news URL details only for persisted events that
are new or still missing at least one enrichment field.

#### Scenario: New event is eligible for detail retrieval
- **WHEN** a base refresh inserts an event whose `description` or `news_url` is null
- **AND** the event has no enrichment attempt in the current UTC day
- **THEN** the event is eligible for a detail request

#### Scenario: Incomplete event is eligible on a later UTC day
- **WHEN** a persisted event still has a null `description` or `news_url`
- **AND** its last enrichment attempt is earlier than the current UTC day
- **THEN** the event is eligible for a detail request

#### Scenario: Complete event is skipped
- **WHEN** a persisted event has both `description` and `news_url`
- **THEN** the refresh does not request details for that event

### Requirement: Economic calendar detail attempts are limited daily

The refresh service SHALL attempt detail retrieval for an event at most once per UTC day.

#### Scenario: Event already attempted today
- **WHEN** an incomplete event has an enrichment attempt timestamp within the current UTC day
- **THEN** subsequent five-minute refreshes do not request its details

#### Scenario: Detail request fails or returns no enrichment
- **WHEN** an eligible event's detail request fails, is malformed, or returns no usable enrichment
- **THEN** the base event remains persisted
- **AND** existing enrichment remains unchanged
- **AND** the event is not attempted again until a later UTC day

### Requirement: Economic calendar provider fetches selected event details

The gateway-owned provider adapter SHALL fetch and normalize details for only the selected upstream
event IDs without adding a new dependency.

#### Scenario: Selected detail is fetched
- **WHEN** the refresh service supplies an eligible calendar type and event ID
- **THEN** the adapter requests the corresponding upstream detail endpoint
- **AND** normalizes description and one related news URL using the existing field rules

#### Scenario: Unselected event is not fetched
- **WHEN** an event ID is not included in the eligible candidate set
- **THEN** the adapter does not request that event's detail endpoint

### Requirement: Economic calendar refresh failure isolation
The economic calendar refresh cronjob SHALL isolate upstream refresh failures from API reads and
other cronjobs.

#### Scenario: Upstream refresh fails
- **WHEN** `market-calendar-tool` fails during a refresh run
- **THEN** the cronjob records a failed run through `CronjobManager`
- **AND** the failure does not stop other registered cronjobs
- **AND** `/v1/economic-calendar` continues to read the last persisted database rows

### Requirement: Economic calendar API remains read-only
The existing `/v1/economic-calendar` endpoint SHALL remain independent from upstream scraping.

#### Scenario: Empty API result does not trigger refresh
- **WHEN** a valid `/v1/economic-calendar` request matches no persisted rows
- **THEN** the API returns a successful empty result
- **AND** does not call `market-calendar-tool`

### Requirement: Economic calendar refresh normalizes descriptions

The provider adapter SHALL normalize a plain-text description from selected detail `specs` rows.

#### Scenario: Measures specification is present
- **WHEN** a selected event detail has a non-empty spec row whose title is `Measures`
- **THEN** the adapter stores that row's text as the event `description`

#### Scenario: Measures specification is absent
- **WHEN** a selected event detail has no usable `Measures` spec row
- **AND** another non-empty spec text exists
- **THEN** the adapter stores the first usable spec text by upstream order as `description`

### Requirement: Economic calendar refresh normalizes one related news URL

The provider adapter SHALL normalize at most one related news URL from selected raw news HTML and
MUST NOT store raw news HTML, news text, or full article content.

#### Scenario: Related hit link is present
- **WHEN** an event has related news HTML containing a `/news/.../hit` link
- **THEN** the adapter stores an absolute `news_url` for the first usable hit link

#### Scenario: Related hit link is absent
- **WHEN** an event has no related news HTML containing a usable hit link
- **THEN** the adapter stores `NULL` for `news_url`

#### Scenario: Full article is not crawled
- **WHEN** the adapter stores a related `news_url`
- **THEN** it does not request the news URL
- **AND** it does not store article content
