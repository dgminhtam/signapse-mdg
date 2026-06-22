# Provider SDK Integration Specification

## Purpose

Define how official provider SDKs are isolated behind gateway-owned adapters while preserving
async service contracts and stable normalized models.

## Requirements

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

### Requirement: Twelve Data Forex integration uses the official SDK

The gateway SHALL use the official Twelve Data Python SDK for the Forex provider foundation and
SHALL keep the SDK behind repository-owned provider adapter boundaries.

#### Scenario: Forex provider dependency is configured

- **WHEN** project dependencies are installed for the gateway
- **THEN** the official `twelvedata` package is available to provider adapter code
- **AND** no Twelve Data SDK type is required by domain, service, cache, database, or API modules

#### Scenario: SDK types are inspected outside the provider package

- **WHEN** domain, service, cache, database, and API modules are analyzed
- **THEN** they contain no imports of Twelve Data SDK clients, request builders, response objects,
  or exceptions

### Requirement: Twelve Data settings are deployment controlled

The gateway SHALL read Twelve Data provider configuration from typed environment settings and
SHALL NOT commit usable Twelve Data credentials.

#### Scenario: Settings are loaded

- **WHEN** application settings are constructed
- **THEN** they include a Twelve Data API key setting
- **AND** they include a Twelve Data REST base URL setting
- **AND** they include a provider timeout setting usable by the Twelve Data adapter

#### Scenario: Placeholder configuration is distributed

- **WHEN** a contributor inspects repository environment examples
- **THEN** Twelve Data settings are documented with placeholder values only
- **AND** no usable Twelve Data API key is present

### Requirement: Twelve Data REST work does not block the event loop

The gateway MUST execute synchronous Twelve Data SDK REST operations outside the ASGI event loop
and SHALL serialize access to any shared Twelve Data SDK client used by the adapter.

#### Scenario: SDK price or time-series operation is slow

- **WHEN** a synchronous Twelve Data SDK REST operation waits for network I/O
- **THEN** unrelated async gateway work can continue on the event loop

#### Scenario: Concurrent calls reach the adapter

- **WHEN** concurrent tasks attempt to use the shared Twelve Data SDK client
- **THEN** the adapter prevents simultaneous access to the shared SDK session

### Requirement: Twelve Data Forex payloads are normalized internally

The Twelve Data adapter foundation SHALL normalize Forex provider payloads into repository-owned
domain-compatible primitives without exposing SDK response structures outside `app/providers/`.

#### Scenario: Latest Forex prices are requested through the adapter

- **WHEN** the adapter receives provider symbols for `EUR/USD`, `GBP/USD`, `USD/JPY`, `AUD/USD`,
  `XAU/USD`, `AAPL`, `TSLA`, `NVDA`, or `MSFT`
- **THEN** it can request Twelve Data latest prices for those provider symbols
- **AND** it returns finite positive prices as `Decimal` values keyed by provider symbol

#### Scenario: Forex time-series candles are requested through the adapter

- **WHEN** the adapter receives a supported gateway timeframe for a Twelve Data Forex symbol
- **THEN** it maps the timeframe to the corresponding Twelve Data interval
- **AND** it can normalize returned OHLCV rows into internal candle-compatible values

#### Scenario: SDK response is invalid or incomplete

- **WHEN** a Twelve Data response is missing required price, time, or OHLC fields, contains an
  invalid decimal, or indicates a provider error
- **THEN** the adapter reports the affected provider symbol as unavailable or raises the
  provider-unavailable boundary
- **AND** it does not expose raw provider error details outside the adapter

### Requirement: Twelve Data WebSocket remains out of scope

This change SHALL NOT implement or wire Twelve Data WebSocket streaming.

#### Scenario: Gateway stream provider is constructed

- **WHEN** the application stream manager is initialized after this change
- **THEN** it continues to use the existing Binance-backed stream provider behavior
- **AND** no Twelve Data WebSocket client is opened by application startup or downstream
  subscriptions
