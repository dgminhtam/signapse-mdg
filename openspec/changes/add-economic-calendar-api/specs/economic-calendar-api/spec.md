## ADDED Requirements

### Requirement: Economic calendar HTTP endpoint

The gateway SHALL expose `GET /v1/economic-calendar` as a read-only endpoint for persisted economic calendar events.

#### Scenario: Return events for a valid time range
- **WHEN** a client requests `GET /v1/economic-calendar` with valid `from` and `to` UTC query parameters
- **THEN** the gateway returns HTTP status `200`
- **AND** the response body includes `from`, `to`, and `events`
- **AND** `events` contains persisted events with `scheduledAt >= from` and `scheduledAt < to`

#### Scenario: Return empty events for an empty range
- **WHEN** a valid request matches no persisted economic calendar events
- **THEN** the gateway returns HTTP status `200`
- **AND** the response body includes `events` as an empty list

### Requirement: Economic calendar response contract

The gateway SHALL return economic calendar events using public field names that do not expose provider/source internals.

#### Scenario: Event response shape
- **WHEN** a persisted economic calendar event is returned
- **THEN** the event includes `key`, `type`, `name`, `currency`, `impact`, `scheduledAt`, `actual`, `forecast`, `previous`, `revision`, `actualBetterWorse`, `revisionBetterWorse`, `firstSeenAt`, `lastSeenAt`, and `lastChangedAt`
- **AND** the event does not include database `id`, `externalEventId`, provider source, or upstream site fields

#### Scenario: Event key is stable public identity
- **WHEN** an event has `type` value `FOREX` and upstream event ID `123456`
- **THEN** the response event `key` is `FOREX:123456`

#### Scenario: Calendar type is public type
- **WHEN** an event is returned
- **THEN** the response event uses `type` with value `FOREX`, `METALS`, `ENERGY`, or `CRYPTO`

### Requirement: Economic calendar query filters

The gateway SHALL support optional filters for calendar type, currency, impact, and result limit.

#### Scenario: Filter by types
- **WHEN** a request includes `types=FOREX,METALS`
- **THEN** the gateway returns only events whose `type` is `FOREX` or `METALS`

#### Scenario: Filter by currencies
- **WHEN** a request includes `currencies=USD,XAU`
- **THEN** the gateway returns only events whose `currency` is `USD` or `XAU`

#### Scenario: Filter by impact
- **WHEN** a request includes `impact=HIGH`
- **THEN** the gateway returns only events whose `impact` is `HIGH`

#### Scenario: Limit results
- **WHEN** a request includes a valid `limit`
- **THEN** the gateway returns no more than that many events

### Requirement: Economic calendar ordering

The gateway SHALL return economic calendar events in deterministic order.

#### Scenario: Events are ordered
- **WHEN** multiple events match a request
- **THEN** events are ordered by `scheduledAt` ascending, then `type` ascending, then `key` ascending

### Requirement: Economic calendar request validation

The gateway SHALL reject malformed economic calendar requests with stable error codes.

#### Scenario: Invalid time range
- **WHEN** `from` or `to` is missing, not UTC, not parseable, or `from` is greater than or equal to `to`
- **THEN** the gateway returns HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Invalid types
- **WHEN** `types` includes a value other than `FOREX`, `METALS`, `ENERGY`, or `CRYPTO`
- **THEN** the gateway returns HTTP status `400`
- **AND** the error code is `INVALID_TYPES`

#### Scenario: Invalid currencies
- **WHEN** `currencies` contains no non-empty value after parsing
- **THEN** the gateway returns HTTP status `400`
- **AND** the error code is `INVALID_CURRENCIES`

#### Scenario: Invalid impact
- **WHEN** `impact` contains no non-empty value after parsing
- **THEN** the gateway returns HTTP status `400`
- **AND** the error code is `INVALID_IMPACT`

#### Scenario: Invalid limit
- **WHEN** `limit` is not an integer or is outside the allowed range
- **THEN** the gateway returns HTTP status `400`
- **AND** the error code is `INVALID_LIMIT`

### Requirement: Economic calendar database failure handling

The gateway SHALL return the shared database unavailable error when persisted economic calendar events cannot be queried.

#### Scenario: Database unavailable
- **WHEN** the economic calendar repository cannot query PostgreSQL
- **THEN** the gateway returns HTTP status `503`
- **AND** the error code is `DATABASE_UNAVAILABLE`

### Requirement: Economic calendar API does not scrape

The gateway SHALL keep `/v1/economic-calendar` independent from upstream economic calendar scraping.

#### Scenario: No scrape on empty result
- **WHEN** a valid request matches no persisted rows
- **THEN** the gateway does not call `market-calendar-tool`
- **AND** returns a successful empty event list
