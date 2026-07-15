## ADDED Requirements

### Requirement: Economic calendar enrichment attempts are persisted

The gateway SHALL persist a nullable timezone-aware `enrichment_attempted_at` timestamp for each
economic calendar event and SHALL use it to select daily enrichment candidates.

#### Scenario: Migration adds enrichment attempt timestamp
- **WHEN** the database schema is migrated
- **THEN** `economic_calendar_events` includes nullable `enrichment_attempted_at`
- **AND** the SQLAlchemy model maps the column

#### Scenario: Repository selects an eligible enrichment candidate
- **WHEN** an event has a null `description` or `news_url`
- **AND** `enrichment_attempted_at` is null or earlier than the current UTC day
- **THEN** the repository can return the event as an enrichment candidate

#### Scenario: Repository records an enrichment attempt
- **WHEN** an event is selected for detail retrieval
- **THEN** the repository stores the current attempt time before the detail request

#### Scenario: Repository skips a candidate attempted today
- **WHEN** an incomplete event has `enrichment_attempted_at` within the current UTC day
- **THEN** the repository does not return it as an enrichment candidate

## MODIFIED Requirements

### Requirement: Economic calendar enrichment participates in upsert change tracking

The gateway SHALL upsert non-null `description` and `news_url` values with the rest of the normalized
event content, SHALL preserve persisted enrichment when an incoming value is null, and SHALL treat
effective changes to either field as event content changes.

#### Scenario: New enriched event is inserted
- **WHEN** a fetched event includes description or news URL
- **THEN** the inserted row stores those values

#### Scenario: Existing enriched event changes
- **WHEN** a fetched event matches an existing row
- **AND** a non-null `description` or `news_url` differs from the persisted value
- **THEN** the gateway updates the field
- **AND** updates `last_seen_at` and `last_changed_at`

#### Scenario: Base refresh has null enrichment
- **WHEN** a base event matches an existing row with stored `description` or `news_url`
- **AND** the incoming enrichment value is null
- **THEN** the gateway preserves the stored enrichment value
- **AND** the null enrichment does not cause `last_changed_at` to change

#### Scenario: Existing enriched event is unchanged
- **WHEN** a fetched event matches an existing row
- **AND** all normalized content fields including effective `description` and `news_url` are unchanged
- **THEN** the gateway updates `last_seen_at`
- **AND** preserves `last_changed_at`
