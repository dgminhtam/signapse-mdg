## ADDED Requirements

### Requirement: Binance Spot integration uses the official SDK

The gateway SHALL use the locked official `binance-sdk-spot` package for Binance Spot REST
operations and SHALL keep the SDK behind the repository-owned provider adapter boundary.

#### Scenario: Latest quotes require Binance data

- **WHEN** the quote service requests uncached Binance provider symbols
- **THEN** the Binance adapter invokes the official SDK `ticker_price` operation
- **AND** no direct HTTP request implementation is used

#### Scenario: SDK types are inspected outside the provider package

- **WHEN** domain, service, cache, and API modules are analyzed
- **THEN** they contain no imports of Binance SDK models, clients, configurations, or exceptions

### Requirement: Synchronous SDK work does not block the event loop

The gateway MUST execute synchronous Binance Spot REST SDK operations outside the ASGI event loop
and SHALL serialize access to the shared SDK REST client.

#### Scenario: SDK quote operation is slow

- **WHEN** the synchronous SDK quote operation is waiting for network I/O
- **THEN** unrelated async gateway work can continue on the event loop

#### Scenario: Concurrent refreshes reach the adapter

- **WHEN** concurrent tasks attempt to use the shared SDK REST client
- **THEN** the adapter prevents simultaneous access to its shared SDK session

### Requirement: SDK configuration preserves provider policy

The gateway SHALL configure the Binance Spot SDK from typed deployment settings, converting the
provider timeout to SDK milliseconds and disabling SDK retries.

#### Scenario: Provider client is constructed

- **WHEN** the Binance SDK REST client is created
- **THEN** its base path equals `BINANCE_REST_BASE_URL`
- **AND** its timeout represents `PROVIDER_HTTP_TIMEOUT_SECONDS` in milliseconds
- **AND** its retries value is `0`
- **AND** no API key or secret is required for latest quotes

### Requirement: SDK responses are normalized into gateway models

The Binance adapter SHALL convert SDK ticker-price response models into
`ProviderQuoteBatch` and SHALL preserve the existing decimal and symbol validation rules.

#### Scenario: SDK returns valid requested prices

- **WHEN** the SDK returns unique entries with finite positive prices for requested symbols
- **THEN** the adapter returns those prices as `Decimal` values keyed by provider symbol

#### Scenario: SDK response contains invalid, duplicate, unexpected, or missing entries

- **WHEN** an SDK response violates a provider payload validation rule
- **THEN** the adapter marks each affected requested symbol unavailable
- **AND** it does not expose the SDK response model outside the adapter

### Requirement: SDK failures remain sanitized

The gateway SHALL translate documented Binance SDK errors, response conversion failures, and
unexpected SDK failures into the existing provider-unavailable boundary without exposing SDK
details.

#### Scenario: SDK raises a documented Binance error

- **WHEN** the SDK raises a network, rate-limit, client, server, or other documented SDK error
- **THEN** the adapter raises `ProviderUnavailableError`
- **AND** the external quote error remains `PROVIDER_UNAVAILABLE`

#### Scenario: Async caller is cancelled

- **WHEN** the task awaiting the SDK operation is cancelled
- **THEN** cancellation propagates through the adapter
- **AND** it is not converted into a provider error

### Requirement: Superseded direct transport is removed

The migration MUST remove production code and tests whose only purpose was direct HTTPX Binance
transport while retaining HTTPX solely where required for application HTTP tests.

#### Scenario: Migration is complete

- **WHEN** the repository is searched for production Binance HTTPX integration
- **THEN** there is no HTTPX application lifespan client or provider HTTP dependency
- **AND** there is no raw Binance URL construction, query JSON encoding, or HTTPX provider error
  handling
- **AND** provider tests use fake SDK boundaries instead of HTTPX `MockTransport`

### Requirement: Latest quote behavior is preserved

The SDK migration MUST NOT change the existing latest-quotes HTTP, registry, cache, freshness, or
per-symbol error requirements.

#### Scenario: Existing quote regression suite runs after migration

- **WHEN** the SDK-backed adapter replaces the direct HTTP implementation
- **THEN** existing `/v1/quotes` contract tests continue to pass without response changes
- **AND** no database migration is introduced
