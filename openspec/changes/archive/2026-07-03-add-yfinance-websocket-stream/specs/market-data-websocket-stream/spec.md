## ADDED Requirements

### Requirement: YFINANCE streams use one shared asynchronous WebSocket

The gateway SHALL use yfinance `AsyncWebSocket` behind a repository-owned stream adapter and SHALL
maintain at most one process-local yfinance WebSocket connection for all active `YFINANCE`
interests.

#### Scenario: First YFINANCE interest is registered

- **WHEN** the first enabled YFINANCE quote or candle interest is registered
- **THEN** the adapter creates one yfinance asynchronous WebSocket client lazily
- **AND** subscribes the persisted provider symbol on that connection
- **AND** starts one listener task

#### Scenario: Additional YFINANCE interests are registered

- **WHEN** additional quote or candle interests reference YFINANCE provider symbols
- **THEN** the adapter reuses the existing WebSocket connection
- **AND** subscribes each provider symbol at most once while it has active references

#### Scenario: Application starts without YFINANCE stream clients

- **WHEN** the application starts and no downstream client requests a YFINANCE asset
- **THEN** no yfinance WebSocket client, connection, subscription, or listener task is created

### Requirement: YFINANCE price ticks produce normalized quote events

The yfinance stream adapter SHALL normalize valid asynchronous price payloads into existing
provider-agnostic quote events without exposing Yahoo or yfinance payload fields.

#### Scenario: Valid subscribed YFINANCE price tick is received

- **WHEN** a decoded payload contains an actively subscribed approved provider symbol, a finite
  positive price, and a valid or absent provider timestamp
- **THEN** the adapter emits one `StreamQuote` using the canonical registry symbol
- **AND** converts the price through its string representation to `Decimal`
- **AND** records gateway receive time in UTC

#### Scenario: YFINANCE price payload is malformed or unrelated

- **WHEN** a payload has an unknown symbol, invalid price, invalid required field, or does not
  represent an active provider-symbol interest
- **THEN** the adapter rejects the payload without updating caches or downstream clients
- **AND** no raw payload or provider exception is exposed

### Requirement: YFINANCE price ticks derive candle events

The gateway SHALL derive YFINANCE stream candles from accepted price ticks for `1m`, `5m`, `15m`,
`1h`, and `1d` interests and SHALL use decimal zero volume.

#### Scenario: First tick creates a forming YFINANCE candle

- **WHEN** the first valid tick lands in an active YFINANCE candle timeframe bucket
- **THEN** the adapter emits a `complete=false` candle aligned to the existing UTC timeframe grid
- **AND** sets open, high, low, and close to the tick price
- **AND** sets volume to exact decimal zero

#### Scenario: Later tick updates the current YFINANCE bucket

- **WHEN** another valid tick lands in the same active candle bucket
- **THEN** the adapter preserves open and updates high, low, and close from accepted tick prices
- **AND** emits the updated candle with `complete=false`

#### Scenario: Tick advances to a later YFINANCE bucket

- **WHEN** a valid tick lands after the current candle bucket
- **THEN** the adapter emits the previous bucket with `complete=true`
- **AND** starts and emits the new bucket with `complete=false`
- **AND** does not synthesize skipped buckets

#### Scenario: Yahoo payload includes day volume

- **WHEN** a valid price tick also contains Yahoo day-level or cumulative volume
- **THEN** the adapter does not treat that value as tick or interval candle volume
- **AND** derived candle volume remains decimal zero

### Requirement: Silent YFINANCE subscriptions remain connecting

The gateway SHALL treat a successful yfinance subscription as active even when Yahoo emits no
usable tick and SHALL NOT add polling, provider-symbol remapping, or cross-provider fallback.

#### Scenario: Subscribed YFINANCE symbol emits no tick

- **WHEN** yfinance accepts a provider-symbol subscription but no valid event has been observed
- **THEN** the downstream quote and candle interests remain in `CONNECTING`
- **AND** the gateway emits no fabricated quote, candle, stale, or provider-error event solely due
  to the absence of a first tick

#### Scenario: Previously active YFINANCE interest stops receiving ticks

- **WHEN** a YFINANCE interest has emitted valid data and later exceeds the configured freshness
  threshold
- **THEN** existing stream freshness behavior can report that interest as `STALE`
- **AND** no fallback provider is selected

### Requirement: YFINANCE stream lifecycle is supervised and deterministic

The yfinance stream adapter SHALL own listener supervision, active-interest resubscription,
unsubscribe behavior, and final shutdown without leaving background tasks running.

#### Scenario: Listener terminates while interests remain

- **WHEN** the yfinance listener raises or returns while active interests remain
- **THEN** the adapter emits `RECONNECTING` for its active interests
- **AND** creates a fresh client after the configured reconnect delay
- **AND** resubscribes the current provider-symbol set before resuming listening

#### Scenario: Final reference to a provider symbol is removed

- **WHEN** no quote or candle interest references a subscribed YFINANCE provider symbol
- **THEN** the adapter unsubscribes that provider symbol
- **AND** leaves other active YFINANCE symbols subscribed

#### Scenario: Final YFINANCE interest is removed

- **WHEN** no YFINANCE stream interest remains
- **THEN** the adapter cancels and awaits its listener supervision
- **AND** closes the yfinance WebSocket connection

#### Scenario: Application shuts down with active YFINANCE interests

- **WHEN** FastAPI lifespan shutdown begins
- **THEN** yfinance subscriptions, listener tasks, and WebSocket resources are closed
  deterministically
- **AND** shutdown leaves no unhandled task exception

## MODIFIED Requirements

### Requirement: Clients can subscribe to canonical real-time market data

The gateway SHALL expose `WS /v1/stream` with required comma-separated `symbols` and required
`timeframe` query parameters. A valid subscription SHALL include both quote and candle events for
each distinct requested canonical symbol, including enabled Binance, Twelve Data, and YFINANCE
symbols.

#### Scenario: Valid multi-symbol subscription

- **WHEN** a client connects with enabled `BTC/USD,ETH/USD` symbols and timeframe `1m`
- **THEN** the gateway accepts one downstream WebSocket connection
- **AND** registers quote and `1m` candle interests for both symbols

#### Scenario: Valid mixed-provider subscription

- **WHEN** a client connects with enabled `BTC/USD,EUR/USD,XAG/USD` symbols and timeframe `1m`
- **THEN** the gateway accepts one downstream WebSocket connection
- **AND** registers quote and `1m` candle interests for all three symbols
- **AND** routes the interests through their persisted Binance, Twelve Data, and YFINANCE mappings

#### Scenario: Duplicate symbols are requested

- **WHEN** a valid subscription repeats a canonical symbol
- **THEN** the gateway subscribes to that symbol once
- **AND** preserves the first occurrence order in status events

### Requirement: Stream interests are routed by persisted provider mapping

The gateway SHALL route each validated stream interest to the stream provider selected by the
enabled symbol's persisted `provider` and `provider_symbol` mapping.

#### Scenario: Mixed-provider subscription is accepted

- **WHEN** a client subscribes to enabled Binance-backed, Twelve Data-backed, and YFINANCE-backed
  symbols in one `/v1/stream` request
- **THEN** the gateway registers quote and candle interests for every requested canonical symbol
- **AND** routes each upstream interest through that symbol's persisted provider mapping

#### Scenario: Unsupported stream provider mapping is requested

- **WHEN** an enabled symbol maps to a provider that has no configured stream adapter
- **THEN** the gateway rejects the affected subscription with sanitized `PROVIDER_UNAVAILABLE`
- **AND** it does not fall back to another provider

#### Scenario: Provider failure is isolated to affected interests

- **WHEN** one upstream provider emits an error signal for its active interests
- **THEN** downstream status events identify only the affected symbols and channels
- **AND** unaffected provider interests can continue receiving normalized events
