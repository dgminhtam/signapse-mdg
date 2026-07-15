## ADDED Requirements

### Requirement: Economic calendar refresh separates base and detail requests

The economic calendar refresh SHALL fetch base values without extended detail retrieval and SHALL
request event details only for persisted enrichment candidates.

#### Scenario: Regular refresh fetches base data only
- **WHEN** the economic calendar refresh runs
- **THEN** the provider adapter calls `market-calendar-tool` with `extended=False` for each supported
  calendar type
- **AND** it does not use the package's full-window extended scrape

#### Scenario: Five-minute production polling remains supported
- **WHEN** `ECONOMIC_CALENDAR_POLL_SECONDS` is configured as `300`
- **THEN** the base refresh runs at the existing five-minute interval
- **AND** detail eligibility is evaluated after the fetched base events are persisted

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

## REMOVED Requirements

### Requirement: Economic calendar refresh fetches extended event details

**Reason**: Full-window `extended=True` scraping performs one detail request per event every five
minutes and has triggered upstream HTTP 403 blocking.

**Migration**: Regular refreshes use `extended=False`; selected new or incomplete events use the
candidate-scoped detail flow no more than once per UTC day.
