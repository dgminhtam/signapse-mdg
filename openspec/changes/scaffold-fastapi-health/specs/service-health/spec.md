## ADDED Requirements

### Requirement: Service health endpoint

The gateway SHALL expose `GET /health` as an unauthenticated process health endpoint.

#### Scenario: Health check succeeds

- **WHEN** a client sends `GET /health`
- **THEN** the gateway responds with HTTP status `200`
- **AND** the response body includes `status` with value `UP`
- **AND** the response body includes `time`

### Requirement: Health timestamp uses UTC

The gateway SHALL return the `time` field as an ISO-8601 UTC timestamp.

#### Scenario: Health response time is UTC

- **WHEN** a client receives a successful `GET /health` response
- **THEN** the `time` value is parseable as an ISO-8601 timestamp
- **AND** the `time` value represents UTC time

### Requirement: Health endpoint does not depend on upstream integrations

The gateway SHALL serve `GET /health` without requiring Binance, PostgreSQL, WebSocket streams, or market-data caches to be initialized.

#### Scenario: Health works before provider and database integrations

- **WHEN** the gateway process is running without provider or database configuration
- **THEN** `GET /health` still responds with HTTP status `200`
- **AND** the response body includes `status` with value `UP`
