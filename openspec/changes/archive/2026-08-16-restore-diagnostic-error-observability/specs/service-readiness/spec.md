## ADDED Requirements

### Requirement: Readiness endpoint reports configured service readiness

The gateway SHALL expose an unauthenticated `GET /ready` endpoint. It SHALL return HTTP `200` with a sanitized body containing `status: READY` and a UTC `time` when required configuration is present and the configured PostgreSQL dependency accepts a connectivity probe. The endpoint SHALL not make live market-data provider calls.

#### Scenario: Configured gateway is ready

- **WHEN** required configuration is present and PostgreSQL connectivity succeeds
- **THEN** `GET /ready` returns HTTP `200`
- **AND** the response contains `status` equal to `READY`
- **AND** the response contains a UTC `time`
- **AND** no provider REST or WebSocket call is made

### Requirement: Readiness failure is safe and diagnosable

The gateway SHALL return HTTP `503` with `status: NOT_READY` and a UTC `time` when required configuration is missing or PostgreSQL connectivity fails. The response SHALL not expose connection strings, credentials, exception text, or provider details. The dependency failure SHALL be recorded in structured logs with safe context.

#### Scenario: Required database configuration is missing

- **WHEN** the deployment requires PostgreSQL but the required database configuration is absent
- **THEN** `GET /ready` returns HTTP `503`
- **AND** the response contains `status` equal to `NOT_READY`
- **AND** the log identifies the missing dependency without exposing secrets

#### Scenario: Database connectivity fails

- **WHEN** the configured PostgreSQL connectivity probe fails
- **THEN** `GET /ready` returns HTTP `503` with `status: NOT_READY`
- **AND** the gateway logs a database readiness failure with safe diagnostic context
- **AND** no market-data provider is called

### Requirement: Liveness remains independent from readiness

The gateway SHALL preserve `GET /health` as an upstream-independent liveness endpoint. Provider configuration, PostgreSQL configuration, and PostgreSQL connectivity SHALL not be required for a successful liveness response.

#### Scenario: Liveness succeeds while dependencies are unavailable

- **WHEN** the gateway process is running without provider access or database connectivity
- **THEN** `GET /health` still returns HTTP `200`
- **AND** the response retains `status: UP` and a UTC `time`
