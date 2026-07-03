## ADDED Requirements

### Requirement: Economic calendar response includes event description and news URL

The gateway SHALL include `description` and `newsUrl` on each economic calendar event response
without exposing raw provider detail payloads.

#### Scenario: Enriched event response shape
- **WHEN** a persisted economic calendar event is returned
- **THEN** the event includes `description` and `newsUrl`
- **AND** the event does not include raw specs, raw news HTML, news text, history rows, provider
  source, database `id`, or upstream site fields

#### Scenario: Enrichment fields are nullable
- **WHEN** a persisted economic calendar event has no description or news URL
- **THEN** the response includes `description: null` or `newsUrl: null`

#### Scenario: News URL is downstream-crawlable
- **WHEN** `newsUrl` is present
- **THEN** it is an absolute URL that downstream consumers can request independently
