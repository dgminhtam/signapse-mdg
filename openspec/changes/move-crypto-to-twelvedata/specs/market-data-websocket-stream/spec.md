## MODIFIED Requirements

### Requirement: Clients can subscribe to canonical real-time market data

The gateway SHALL expose `WS /v1/stream` with required comma-separated `symbols` and required
`timeframe` query parameters. A valid subscription SHALL include both quote and candle events for
each distinct requested canonical symbol, including enabled crypto and Forex symbols.

#### Scenario: Valid multi-symbol subscription
- **WHEN** a client connects with enabled `BTC/USD,ETH/USD` symbols and timeframe `1m`
- **THEN** the gateway accepts one downstream WebSocket connection
- **AND** registers quote and `1m` candle interests for both symbols

#### Scenario: Valid mixed-catalog subscription
- **WHEN** a client connects with enabled `BTC/USD,EUR/USD` symbols and timeframe `1m`
- **THEN** the gateway accepts one downstream WebSocket connection
- **AND** registers quote and `1m` candle interests for both symbols
- **AND** routes both interests using their persisted Twelve Data mappings

#### Scenario: Duplicate symbols are requested
- **WHEN** a valid subscription repeats a canonical symbol
- **THEN** the gateway subscribes to that symbol once
- **AND** preserves the first occurrence order in status events

### Requirement: Stream interests are routed by persisted provider mapping

The gateway SHALL route each validated stream interest to the stream provider selected by the
enabled symbol's persisted `provider` and `provider_symbol` mapping.

#### Scenario: Twelve Data crypto and Forex subscription is accepted

- **WHEN** a client subscribes to enabled `BTC/USD` and `EUR/USD` in one `/v1/stream` request
- **THEN** the gateway registers quote and candle interests for every requested canonical symbol
- **AND** it routes each upstream interest through that symbol's persisted Twelve Data mapping

#### Scenario: Unsupported stream provider mapping is requested

- **WHEN** an enabled symbol maps to a provider that has no configured stream adapter
- **THEN** the gateway rejects the affected subscription with sanitized `PROVIDER_UNAVAILABLE`
- **AND** it does not fall back to another provider

#### Scenario: Provider failure is isolated to affected interests

- **WHEN** one upstream provider emits an error signal for its active interests
- **THEN** downstream status events identify only the affected symbols and channels
- **AND** unaffected provider interests can continue receiving normalized events

## ADDED Requirements

### Requirement: Twelve Data crypto streams use the shared upstream WebSocket

The gateway SHALL serve enabled `BTC/USD` and `ETH/USD` stream interests through the shared
Twelve Data WebSocket when those symbols are mapped to `TWELVE_DATA`.

#### Scenario: Crypto subscription is opened
- **WHEN** a client subscribes to `BTC/USD` or `ETH/USD`
- **THEN** quote and candle interests use the persisted `TWELVE_DATA` mapping
- **AND** the Twelve Data stream adapter subscribes the matching provider symbol
