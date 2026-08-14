## MODIFIED Requirements

### Requirement: Clients can subscribe to canonical real-time market data

The gateway SHALL expose `WS /v1/stream` with required comma-separated `symbols`, required `timeframe`, and at most one optional case-sensitive `provider` query value. A valid subscription SHALL include both quote and candle events for each distinct requested canonical symbol, and one Provider Override SHALL apply to every symbol in the subscription.

#### Scenario: Valid multi-symbol default subscription

- **WHEN** a client connects with enabled `BTC/USD,ETH/USD` symbols and timeframe `1m` without `provider`
- **THEN** the gateway accepts one downstream WebSocket connection
- **AND** registers quote and `1m` candle interests through each symbol's Default Provider

#### Scenario: Valid override subscription

- **WHEN** a client connects with enabled symbols that all support the requested Provider Override
- **THEN** the gateway accepts one downstream WebSocket connection
- **AND** registers quote and candle interests for every symbol through the requested mapping

#### Scenario: Duplicate symbols are requested

- **WHEN** a valid subscription repeats a canonical symbol
- **THEN** the gateway subscribes to that symbol once
- **AND** preserves the first occurrence order in status events

### Requirement: The complete subscription is validated before provider access

The gateway MUST validate request shape, including Provider Override cardinality and content, the configured distinct-symbol limit, every symbol against the enabled PostgreSQL registry, the timeframe against the supported timeframe map, and the requested Provider Mapping for every symbol before opening or extending an upstream subscription. Validation MUST be all-or-nothing and MUST follow request shape, canonical asset, then Provider Mapping precedence.

#### Scenario: Provider parameter is empty or repeated

- **WHEN** `provider` is empty, whitespace-only, or appears more than once
- **THEN** the gateway closes the downstream connection with WebSocket code `1008`
- **AND** the close reason is `INVALID_PROVIDER`
- **AND** no registry lookup or provider subscription is opened

#### Scenario: Symbols parameter is missing or empty

- **WHEN** `symbols` is missing, empty, or contains only commas and whitespace
- **THEN** the gateway closes the downstream connection with WebSocket code `1008`
- **AND** the close reason is `INVALID_SYMBOLS`
- **AND** no provider subscription is opened

#### Scenario: Too many symbols are requested

- **WHEN** the distinct symbol count exceeds `MAX_QUOTE_SYMBOLS`
- **THEN** the gateway closes the downstream connection with WebSocket code `1008`
- **AND** the close reason is `TOO_MANY_SYMBOLS`
- **AND** no provider subscription is opened

#### Scenario: Any symbol is unknown or disabled

- **WHEN** one or more requested symbols have no enabled registry record
- **THEN** the complete subscription is rejected with WebSocket code `1008`
- **AND** the close reason is `UNSUPPORTED_SYMBOL`
- **AND** Provider Mapping validation does not replace that error
- **AND** no partial upstream subscription is opened

#### Scenario: Any symbol lacks the requested mapping

- **WHEN** every requested symbol is enabled but one or more lack a Provider Mapping matching the override
- **THEN** the complete subscription is rejected with WebSocket code `1008`
- **AND** the close reason is `UNSUPPORTED_PROVIDER`
- **AND** no partial upstream subscription is opened
- **AND** no symbol falls back to its Default Provider

#### Scenario: Timeframe is missing or unsupported

- **WHEN** `timeframe` is absent or is not one of `1m`, `5m`, `15m`, `1h`, `4h`, or `1d`
- **THEN** the gateway closes the downstream connection with WebSocket code `1008`
- **AND** the close reason is `UNSUPPORTED_TIMEFRAME`
- **AND** no provider subscription is opened

#### Scenario: Registry validation is unavailable

- **WHEN** PostgreSQL cannot validate the requested symbols or an enabled asset has no Default Provider
- **THEN** the gateway closes the downstream connection with WebSocket code `1011`
- **AND** the close reason is `DATABASE_UNAVAILABLE`
- **AND** an explicit Provider Override does not bypass an invalid registry state
- **AND** no database detail or credential is exposed

### Requirement: Matching upstream subscriptions are shared and lazy

The stream manager and provider router SHALL maintain process-local reference counts for upstream interests identified by canonical symbol, Provider Identifier, provider symbol, channel, and timeframe where applicable. They SHALL open an interest only for the first downstream consumer resolving to that exact Provider Mapping and SHALL remove it only after the final matching consumer leaves.

#### Scenario: Two clients request the same selected series

- **WHEN** two downstream clients resolve to the same Provider Mapping, symbol, and timeframe
- **THEN** they share one quote interest and one candle interest upstream
- **AND** both clients receive matching normalized events

#### Scenario: Two clients select different mappings

- **WHEN** two downstream clients select different Provider Mappings for the same canonical symbol and timeframe
- **THEN** they use independent quote and candle interests
- **AND** events from one selection are not fanned out to the other

#### Scenario: One of multiple clients disconnects

- **WHEN** one client leaves while another still needs the same selected upstream interest
- **THEN** the upstream subscription remains active

#### Scenario: Final client disconnects

- **WHEN** the final client for a selected upstream interest disconnects
- **THEN** the manager unsubscribes that provider stream after the configured idle grace period
- **AND** closes the provider connection when no upstream interests for that provider remain

### Requirement: Stream interests are routed by persisted provider mapping

The gateway SHALL route every validated stream interest through the immutable Provider Selection resolved from the enabled canonical symbol's normalized mappings. When `provider` is omitted it MUST use the Default Provider; when supplied it MUST use the exact configured mapping regardless of default state. It MUST use the same selected identity for quote and candle interests and MUST NOT automatically fall back.

#### Scenario: Mixed-provider default subscription is accepted

- **WHEN** a client omits Provider Override and subscribes to enabled symbols with different Default Providers
- **THEN** the gateway registers quote and candle interests for every requested canonical symbol
- **AND** routes each interest through that symbol's Default Provider

#### Scenario: Override subscription is accepted

- **WHEN** every requested enabled symbol has the Provider Mapping named by the override
- **THEN** the gateway routes every quote and candle interest through those selected mappings
- **AND** leaves each symbol's Default Provider unchanged

#### Scenario: Default Provider changes before a new subscription

- **WHEN** a symbol's Default Provider changes before a subsequent subscription is resolved
- **THEN** a new default subscription uses the newly selected provider and provider symbol
- **AND** an existing connection remains on its original Provider Selection

#### Scenario: Selected stream adapter is unavailable

- **WHEN** a configured Provider Mapping has no usable stream adapter or cannot establish its upstream subscription
- **THEN** the gateway closes the downstream connection with WebSocket code `1011`
- **AND** the close reason is `PROVIDER_UNAVAILABLE`
- **AND** it does not fall back to another Provider Mapping

#### Scenario: Provider failure is isolated to affected interests

- **WHEN** one upstream provider emits an error signal after interests are active
- **THEN** downstream status events identify only the affected symbols and channels
- **AND** unaffected provider interests can continue receiving normalized events until connection-level failure handling applies

