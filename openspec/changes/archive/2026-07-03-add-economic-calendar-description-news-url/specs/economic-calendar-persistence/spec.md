## ADDED Requirements

### Requirement: Economic calendar events store description and news URL

The gateway SHALL persist optional plain-text description and optional related news URL fields for
each economic calendar event.

#### Scenario: Description and news URL columns are migrated
- **WHEN** the database schema is migrated
- **THEN** `economic_calendar_events` includes nullable `description` and `news_url` text columns

#### Scenario: Model maps enrichment fields
- **WHEN** application models are loaded
- **THEN** the economic calendar event model maps `description` and `news_url`

### Requirement: Economic calendar enrichment participates in upsert change tracking

The gateway SHALL upsert `description` and `news_url` with the rest of the normalized event content
and SHALL treat changes to either field as event content changes.

#### Scenario: New enriched event is inserted
- **WHEN** a fetched event includes description or news URL
- **THEN** the inserted row stores those values

#### Scenario: Existing enriched event changes
- **WHEN** a fetched event matches an existing row
- **AND** `description` or `news_url` differs from the persisted row
- **THEN** the gateway updates the field
- **AND** updates `last_seen_at` and `last_changed_at`

#### Scenario: Existing enriched event is unchanged
- **WHEN** a fetched event matches an existing row
- **AND** all normalized content fields including `description` and `news_url` are unchanged
- **THEN** the gateway updates `last_seen_at`
- **AND** preserves `last_changed_at`
