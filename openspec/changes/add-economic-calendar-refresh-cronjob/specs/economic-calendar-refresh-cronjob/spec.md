## ADDED Requirements

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
