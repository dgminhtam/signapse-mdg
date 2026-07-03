## Purpose

Defines the persisted economic calendar event schema, identity, indexing, model mapping, and upsert behavior.

## Requirements

### Requirement: Economic calendar event table

The gateway SHALL define an `economic_calendar_events` table for normalized economic calendar base events.

#### Scenario: Table has required event identity and display fields
- **WHEN** the database schema is migrated
- **THEN** `economic_calendar_events` exists
- **AND** it includes `id`, `calendar_type`, `external_event_id`, `name`, `currency`, `impact`, and `scheduled_at`

#### Scenario: Table has required calendar value fields
- **WHEN** the database schema is migrated
- **THEN** `economic_calendar_events` includes `actual`, `forecast`, `previous`, `revision`, `actual_better_worse`, and `revision_better_worse`
- **AND** those value fields are nullable text fields

#### Scenario: Table has required lifecycle timestamps
- **WHEN** the database schema is migrated
- **THEN** `economic_calendar_events` includes `first_seen_at`, `last_seen_at`, `last_changed_at`, `created_at`, and `updated_at`
- **AND** those timestamp fields are timezone-aware and non-null

### Requirement: Economic calendar event identity

The gateway SHALL enforce one persisted row per economic calendar type and upstream event ID.

#### Scenario: Unique event identity
- **WHEN** two rows have the same `calendar_type` and `external_event_id`
- **THEN** the database rejects the duplicate identity

#### Scenario: Same upstream ID across different types
- **WHEN** two rows have the same `external_event_id` and different `calendar_type` values
- **THEN** the database allows both rows

### Requirement: Economic calendar type constraint

The gateway SHALL restrict persisted economic calendar types to the supported public calendar types.

#### Scenario: Supported calendar type is accepted
- **WHEN** a row uses `calendar_type` with value `FOREX`, `METALS`, `ENERGY`, or `CRYPTO`
- **THEN** the database accepts the value

#### Scenario: Unsupported calendar type is rejected
- **WHEN** a row uses any other `calendar_type` value
- **THEN** the database rejects the value

### Requirement: Economic calendar query indexes

The gateway SHALL add indexes that support expected economic calendar range queries.

#### Scenario: Query by scheduled time
- **WHEN** the schema is inspected
- **THEN** an index exists on `scheduled_at`

#### Scenario: Query by calendar type and scheduled time
- **WHEN** the schema is inspected
- **THEN** an index exists on `calendar_type` and `scheduled_at`

#### Scenario: Query by currency and scheduled time
- **WHEN** the schema is inspected
- **THEN** an index exists on `currency` and `scheduled_at`

### Requirement: Economic calendar model

The gateway SHALL define a SQLAlchemy model for the economic calendar event table.

#### Scenario: Model maps to table schema
- **WHEN** application models are loaded
- **THEN** the economic calendar event model maps to `economic_calendar_events`
- **AND** its columns match the migration schema

### Requirement: No economic calendar behavior logic

The gateway SHALL keep this change limited to persistence schema and model definitions.

#### Scenario: No provider or API behavior is added
- **WHEN** this change is implemented
- **THEN** it does not add economic calendar provider fetch logic, cronjob refresh logic, REST routes, WebSocket routes, or fanout behavior

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
