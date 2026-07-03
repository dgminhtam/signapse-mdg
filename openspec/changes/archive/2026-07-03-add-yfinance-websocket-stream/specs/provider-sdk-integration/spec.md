## ADDED Requirements

### Requirement: yfinance asynchronous WebSocket details remain provider-local

The gateway SHALL isolate yfinance asynchronous WebSocket clients, decoded payloads, configuration,
tasks, and exceptions inside `app/providers/`.

#### Scenario: Production boundaries are inspected

- **WHEN** domain, service, cache, database, and API modules are analyzed
- **THEN** they contain no imports of yfinance WebSocket clients, pricing payload models, or
  exceptions
- **AND** they interact with the adapter only through repository-owned stream models and protocols

### Requirement: yfinance stream operations use public asynchronous SDK methods

The gateway SHALL use the locked yfinance package's public `AsyncWebSocket` operations for
connection, subscription, listening, unsubscribe, and close behavior.

#### Scenario: YFINANCE provider symbol is subscribed

- **WHEN** the adapter opens an approved YFINANCE provider-symbol interest
- **THEN** it uses `AsyncWebSocket.subscribe` with the persisted provider symbol
- **AND** consumes decoded messages through `AsyncWebSocket.listen`

#### Scenario: YFINANCE provider symbol is released

- **WHEN** the final reference for a provider symbol is removed
- **THEN** the adapter uses `AsyncWebSocket.unsubscribe` for that provider symbol

#### Scenario: Stream adapter is closed

- **WHEN** the adapter has no remaining interests or application shutdown begins
- **THEN** it uses `AsyncWebSocket.close`
- **AND** cancels and awaits adapter-owned tasks

### Requirement: yfinance WebSocket failures remain sanitized

The gateway SHALL translate yfinance connection, subscription, listener, unsubscribe, decode, and
close failures into existing provider lifecycle behavior without exposing SDK details publicly.

#### Scenario: Initial connection or subscription fails

- **WHEN** yfinance cannot establish or subscribe the first required provider-symbol interest
- **THEN** the adapter raises `ProviderUnavailableError`
- **AND** the downstream connection receives only the existing sanitized provider-unavailable
  behavior

#### Scenario: Active listener terminates unexpectedly

- **WHEN** the yfinance listener fails after interests are registered
- **THEN** the adapter emits a repository-owned reconnecting signal for affected interests
- **AND** no SDK exception text, URL, or raw payload reaches downstream clients

#### Scenario: Adapter task is cancelled

- **WHEN** application shutdown or interest cleanup cancels adapter-owned asynchronous work
- **THEN** cancellation is treated as lifecycle control
- **AND** it is not converted into a provider error

## RENAMED Requirements

- FROM: `### Requirement: yfinance market-data routing remains out of scope`
- TO: `### Requirement: yfinance market data uses repository-owned adapters`

## MODIFIED Requirements

### Requirement: yfinance market data uses repository-owned adapters

The gateway SHALL route enabled `YFINANCE` symbols through repository-owned yfinance adapters for
latest quotes, historical candles, and WebSocket market data while preserving provider-agnostic
domain and public contracts.

#### Scenario: Public market-data routes use YFINANCE mappings

- **WHEN** an enabled YFINANCE registry row is requested through quote, candle, or WebSocket routes
- **THEN** the gateway routes the persisted provider symbol to the matching yfinance adapter
- **AND** existing Binance and Twelve Data behavior remains unchanged
- **AND** no automatic fallback or provider-symbol remapping occurs

#### Scenario: Application starts after YFINANCE stream integration

- **WHEN** the gateway application starts without active downstream YFINANCE stream interests
- **THEN** no yfinance network request, WebSocket connection, subscription, or background task is
  opened
- **AND** yfinance provider state is initialized lazily when the corresponding operation is needed
