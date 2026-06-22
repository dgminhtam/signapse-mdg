## ADDED Requirements

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

- **WHEN** the adapter receives provider symbols for `EUR/USD`, `GBP/USD`, `USD/JPY`, or `AUD/USD`
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
