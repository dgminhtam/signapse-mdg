## MODIFIED Requirements

### Requirement: Twelve Data settings are deployment controlled

The gateway SHALL read Twelve Data provider configuration from typed environment settings, SHALL
support one or more configured Twelve Data API keys for Twelve Data only, and SHALL NOT commit
usable Twelve Data credentials.

#### Scenario: Settings are loaded

- **WHEN** application settings are constructed
- **THEN** they include a Twelve Data API key setting
- **AND** they include a Twelve Data API keys setting for comma-separated multiple keys
- **AND** they include a Twelve Data REST base URL setting
- **AND** they include a provider timeout setting usable by the Twelve Data adapter

#### Scenario: Placeholder configuration is distributed

- **WHEN** a contributor inspects repository environment examples
- **THEN** Twelve Data settings are documented with placeholder values only
- **AND** no usable Twelve Data API key is present

#### Scenario: Single-key configuration remains compatible

- **WHEN** deployment provides only the existing single Twelve Data API key setting
- **THEN** Twelve Data REST and stream providers can still be constructed with that key

#### Scenario: Multiple keys are configured

- **WHEN** deployment provides comma-separated Twelve Data API keys
- **THEN** the gateway builds an ordered de-duplicated effective key list for Twelve Data
- **AND** no other provider receives those keys

## ADDED Requirements

### Requirement: Twelve Data REST rotates configured API keys
The Twelve Data REST adapter SHALL choose among configured healthy Twelve Data API keys inside the
provider boundary and SHALL keep SDK clients, keys, and provider exceptions out of domain, service,
cache, database, and API modules.

#### Scenario: REST request uses the next healthy key
- **WHEN** a Twelve Data REST quote or candle operation requires live provider data
- **THEN** the adapter selects a healthy configured Twelve Data key for the SDK client
- **AND** the public response shape remains unchanged

#### Scenario: Selected key is temporarily unavailable
- **WHEN** a Twelve Data REST operation fails with a key-related provider failure such as quota,
  rate-limit, or authentication exhaustion
- **THEN** the adapter marks that key unavailable for a short process-local cooldown
- **AND** it retries the same operation at most once with another healthy configured key

#### Scenario: No alternate key is healthy
- **WHEN** a Twelve Data REST operation requires live provider data and no configured key is
  currently usable
- **THEN** the adapter raises the sanitized provider-unavailable boundary
- **AND** it does not expose any API key, raw provider payload, SDK exception, or credential detail

#### Scenario: Provider reports no candle data
- **WHEN** Twelve Data returns the recognized no-data time-series condition for a valid candle range
- **THEN** the adapter preserves the existing successful empty-candle behavior
- **AND** it does not cool down the selected key

### Requirement: Twelve Data WebSocket key selection occurs at connection boundaries
The Twelve Data stream adapter SHALL choose a configured Twelve Data API key when opening a
WebSocket connection and MUST NOT rotate keys on a live connected WebSocket subscription.

#### Scenario: Stream connection is opened
- **WHEN** the first active Twelve Data stream interest requires a WebSocket connection
- **THEN** the adapter selects one configured healthy Twelve Data key to construct the SDK
  WebSocket client

#### Scenario: Stream connection remains active
- **WHEN** a Twelve Data WebSocket connection is already active
- **THEN** new subscriptions reuse the active connection
- **AND** no live key rotation occurs

#### Scenario: Stream reconnects after failure
- **WHEN** the Twelve Data stream adapter must create a new WebSocket connection after disconnect
  or provider failure
- **THEN** it may select another healthy configured Twelve Data key at that reconnect boundary
