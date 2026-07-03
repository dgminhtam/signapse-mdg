## ADDED Requirements

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
