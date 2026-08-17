# Market Data WebSocket Stream Specification

## Purpose

Define the provider-agnostic real-time market data WebSocket contract, validation, upstream
subscription sharing, fanout, cache integration, persistence handoff, and lifecycle behavior.
## Requirements
### Requirement: Clients can subscribe to canonical real-time market data

The gateway SHALL expose `WS /v1/stream` with required comma-separated `symbols` and at most one
optional case-sensitive `provider` query value. The request SHALL NOT include `timeframe`. A valid
subscription SHALL deliver quote events only for each distinct requested canonical symbol, and one
Provider Override SHALL apply to every symbol in the subscription.

#### Scenario: Valid multi-symbol default subscription

- **WHEN** a client connects with enabled `BTC/USD,ETH/USD` symbols without `provider` or `timeframe`
- **THEN** the gateway accepts one downstream WebSocket connection
- **AND** registers one quote interest per symbol through each symbol's Default Provider
- **AND** emits lifecycle status events with `channels: ["quote"]`

#### Scenario: Valid mixed-catalog default subscription

- **WHEN** a client connects with enabled `BTC/USD,EUR/USD` symbols without `provider` or `timeframe`
- **THEN** the gateway accepts one downstream WebSocket connection
- **AND** registers one quote interest per symbol
- **AND** routes each interest using its persisted Default Provider mapping

#### Scenario: Valid override subscription

- **WHEN** a client connects with enabled symbols that all support the requested Provider Override
  and omits `timeframe`
- **THEN** the gateway accepts one downstream WebSocket connection
- **AND** registers one quote interest per symbol through the requested mapping

#### Scenario: Duplicate symbols are requested
- **WHEN** a valid subscription repeats a canonical symbol
- **THEN** the gateway subscribes to that symbol once
- **AND** preserves the first occurrence order in status events

#### Scenario: No initial quote snapshot is sent
- **WHEN** a valid quote-only subscription is registered
- **THEN** the gateway does not synthesize or send an initial quote snapshot
- **AND** the client can use `GET /v1/quotes` for an initial/latest quote
### Requirement: The complete subscription is validated before provider access

The gateway MUST validate request shape, including Provider Override cardinality and content, the
configured distinct-symbol limit, every symbol against the enabled PostgreSQL registry, and the
requested Provider Mapping for every symbol before opening or extending an upstream subscription.
Validation MUST be all-or-nothing and MUST follow request shape, canonical asset, then Provider
Mapping precedence. Any presence of a `timeframe` query parameter is invalid for this endpoint.

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

#### Scenario: Timeframe is present on the quote stream
- **WHEN** `timeframe` is present with an empty value or any candle value such as `1m` or `1w`
- **THEN** the gateway closes the downstream connection with WebSocket code `1008`
- **AND** the close reason is `TIMEFRAME_NOT_ALLOWED`
- **AND** no registry lookup or provider subscription is opened

#### Scenario: Registry validation is unavailable
- **WHEN** PostgreSQL cannot validate the requested symbols or an enabled asset has no Default Provider
- **THEN** the gateway closes the downstream connection with WebSocket code `1011`
- **AND** the close reason is `DATABASE_UNAVAILABLE`
- **AND** an explicit Provider Override does not bypass an invalid registry state
- **AND** no database detail or credential is exposed

### Requirement: Public quote events are minimal and provider-agnostic
Each public quote event SHALL contain exactly `type`, `symbol`, `price`, and `receivedAt`.
`type` SHALL be `quote`; price SHALL be a fixed-point decimal string; and `receivedAt` SHALL be
the UTC time at which the gateway received and normalized the provider event.

#### Scenario: Valid ticker event is received
- **WHEN** Binance sends a valid ticker event for a subscribed provider symbol
- **THEN** the gateway emits one quote event using the canonical symbol and latest ticker price
- **AND** the event contains no asset class, provider identity, provider symbol, volume, provider
  timestamp, or per-event stale field

#### Scenario: Quote decimal has an exponent representation
- **WHEN** a normalized quote Decimal can be represented with exponent notation
- **THEN** the public price is serialized in fixed-point notation
- **AND** no binary floating-point conversion or scientific notation is used

### Requirement: Status events describe downstream stream lifecycle

The gateway SHALL emit provider-agnostic status events containing exactly `type`, `state`,
`symbols`, `channels`, and `observedAt`, except that an `ERROR` event SHALL additionally contain
`code` and `message`. For this quote-only stream, `channels` SHALL always be exactly `["quote"]`.
Supported states SHALL include `CONNECTING`, `SUBSCRIBED`, `STALE`, `RECONNECTING`, and `ERROR`;
the gateway SHALL NOT emit `MARKET_CLOSED`.

#### Scenario: Valid connection begins upstream setup
- **WHEN** a validated downstream connection is registered but no valid quote has been received
- **THEN** the gateway emits `CONNECTING` for the requested symbols and `channels: ["quote"]`

#### Scenario: All required streams become available
- **WHEN** the first valid normalized quote is received for a registered quote subscription
- **THEN** the gateway emits `SUBSCRIBED` for the requested symbols and `channels: ["quote"]`

#### Scenario: One or more required streams become stale
- **WHEN** no valid quote has been received for longer than
  `QUOTE_STALE_AFTER_SECONDS`
- **THEN** the gateway emits `STALE`
- **AND** `symbols` and `channels` identify the quote-only subscription

#### Scenario: Fresh data resumes after stale state
- **WHEN** a new valid quote is received after the subscription was stale
- **THEN** the gateway emits `SUBSCRIBED` once for the recovered state

#### Scenario: Upstream reconnect is observed
- **WHEN** the provider adapter detects connection loss or an SDK reconnect cycle
- **THEN** affected downstream clients receive `RECONNECTING`
- **AND** subscriptions remain registered for automatic resubscription

#### Scenario: Stream cannot continue
- **WHEN** an unrecoverable provider or stream-manager failure prevents serving a registered
  subscription
- **THEN** the gateway emits `ERROR` with sanitized `PROVIDER_UNAVAILABLE` code and message
- **AND** `channels` is exactly `["quote"]`
- **AND** closes the downstream connection with WebSocket code `1011`

### Requirement: Binance streams use the official SDK behind an adapter
The Binance adapter SHALL use the official Spot SDK WebSocket Streams API for individual-symbol
ticker streams only and MUST isolate all SDK models, callbacks, handles, exceptions, and provider
naming inside the provider boundary. WebSocket kline access remains an HTTP candle-provider
concern, not a stream subscription.

#### Scenario: First quote subscription needs Binance streams
- **WHEN** a requested quote interest has no active upstream subscription
- **THEN** the adapter creates an SDK WebSocket stream connection if needed
- **AND** subscribes to the lowercase `<provider-symbol>@ticker` stream through SDK operations

#### Scenario: SDK callback receives valid ticker data
- **WHEN** the SDK invokes a ticker callback
- **THEN** the adapter validates the provider symbol, event time, and latest price
- **AND** enqueues a repository-owned normalized quote event without awaiting downstream I/O

#### Scenario: Provider payload is malformed
- **WHEN** an SDK callback contains missing, non-finite, inconsistent, duplicate, or unexpected
  data
- **THEN** the adapter rejects that event without exposing the payload to clients
- **AND** records a sanitized provider error

### Requirement: Matching upstream subscriptions are shared and lazy

The stream manager and provider router SHALL maintain process-local reference counts for upstream
quote interests identified by canonical symbol, Provider Identifier, and provider symbol. They
SHALL open an interest only for the first downstream consumer resolving to that exact Provider
Mapping and SHALL remove it only after the final matching consumer leaves.

#### Scenario: Two clients request the same selected quote series

- **WHEN** two downstream clients resolve to the same Provider Mapping and canonical symbol
- **THEN** they share one quote interest upstream
- **AND** both clients receive matching normalized quote events

#### Scenario: Two clients select different mappings

- **WHEN** two downstream clients select different Provider Mappings for the same canonical symbol
- **THEN** they use independent quote interests
- **AND** events from one selection are not fanned out to the other

#### Scenario: One of multiple clients disconnects
- **WHEN** one client leaves while another still needs the same upstream interest
- **THEN** the upstream subscription remains active

#### Scenario: Final client disconnects
- **WHEN** the final client for an upstream interest disconnects
- **THEN** the manager unsubscribes that provider stream after the configured idle grace period
- **AND** closes the provider connection when no upstream interests for that provider remain

### Requirement: Fanout isolates provider consumption from downstream speed
The stream manager MUST use a bounded per-client queue and a dedicated sender task so provider
callbacks, cache updates, persistence work, and other downstream clients are not blocked by one
slow client.

#### Scenario: Client keeps pace with events
- **WHEN** a client's queue has capacity
- **THEN** matching events are delivered in the order accepted by that client queue

#### Scenario: Client queue reaches capacity
- **WHEN** a downstream client's bounded queue cannot accept another event
- **THEN** the gateway disconnects that client with WebSocket code `1013`
- **AND** other clients and upstream consumption continue

#### Scenario: Downstream client disconnects unexpectedly
- **WHEN** receive or send detects a client disconnect
- **THEN** the sender task and subscription registration are cleaned up idempotently

### Requirement: Stream resources follow application lifecycle
The gateway SHALL own the stream manager, provider adapter, monitors, SDK session, and background
tasks through FastAPI application lifespan and SHALL clean them up deterministically.

#### Scenario: Application starts without stream clients
- **WHEN** the application starts
- **THEN** no Binance WebSocket connection is opened

#### Scenario: Application shuts down with active streams
- **WHEN** application shutdown begins
- **THEN** downstream sender and monitor tasks are cancelled and awaited
- **AND** SDK subscriptions, WebSocket connections, and sessions are closed
- **AND** shutdown does not leave unhandled background-task exceptions

### Requirement: Stream settings use typed deployment configuration

The gateway SHALL provide validated typed settings for Binance WebSocket base URL, Twelve Data
WebSocket enablement and heartbeat behavior, SDK reconnect delay, downstream queue capacity,
upstream idle grace period, and freshness monitor interval.

#### Scenario: Stream settings are omitted
- **WHEN** stream-specific environment variables are absent
- **THEN** the gateway uses documented non-secret defaults suitable for the single-process MVP
- **AND** Forex streaming requires valid Twelve Data API key configuration before live provider
  access

#### Scenario: Invalid stream setting is supplied
- **WHEN** a queue capacity, reconnect delay, heartbeat interval, idle grace period, or monitor
  interval violates its numeric constraints
- **THEN** application configuration validation fails explicitly

### Requirement: WTI and ETF symbols use the shared Twelve Data stream

The gateway SHALL serve enabled WTI, SPY, and QQQ through the shared Twelve Data WebSocket.

#### Scenario: New symbol subscription is opened
- **WHEN** a client subscribes to `WTI`, `SPY`, or `QQQ`
- **THEN** interests use the persisted `TWELVE_DATA` mapping

#### Scenario: Mixed Twelve Data assets are subscribed
- **WHEN** Forex, WTI, and ETF interests are concurrent
- **THEN** one process-local Twelve Data connection is reused

### Requirement: WTI and ETF price events produce normalized streams

The adapter SHALL normalize valid WTI, SPY, and QQQ prices into the existing provider-agnostic
quote event shape. It SHALL NOT derive or emit WebSocket candle events.

#### Scenario: Valid price event is received
- **WHEN** Twelve Data emits a valid event for a subscribed new asset
- **THEN** the existing provider-agnostic quote shape is emitted
- **AND** no candle interest, candle event, cache update, or persistence handoff is created

### Requirement: Stream interests are routed by persisted provider mapping

The gateway SHALL route every validated quote stream interest through the immutable Provider
Selection resolved from the enabled canonical symbol's normalized mappings. When `provider` is
omitted it MUST use the Default Provider; when supplied it MUST use the exact configured mapping
regardless of default state. It MUST NOT automatically fall back.

#### Scenario: Mixed-provider default subscription is accepted

- **WHEN** a client omits Provider Override and subscribes to enabled symbols with different Default Providers
- **THEN** the gateway registers quote interests for every requested canonical symbol
- **AND** routes each interest through that symbol's Default Provider

#### Scenario: Override subscription is accepted

- **WHEN** every requested enabled symbol has the Provider Mapping named by the override
- **THEN** the gateway routes every quote interest through those selected mappings
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

- **WHEN** one upstream provider emits an error signal for its active interests
- **THEN** downstream status events identify only the affected symbols and channels
- **AND** unaffected provider interests can continue receiving normalized events
### Requirement: Twelve Data Forex streams use one shared upstream WebSocket

The Twelve Data Forex stream adapter SHALL use the official `twelvedata` SDK WebSocket object
behind the provider boundary and SHALL maintain at most one process-local Twelve Data WebSocket
connection for all active Forex stream interests.

#### Scenario: First Forex subscription opens Twelve Data WebSocket

- **WHEN** the first Twelve Data-backed Forex quote interest is registered
- **THEN** the adapter creates and connects one SDK WebSocket object
- **AND** it subscribes the required provider symbols on that connection

#### Scenario: Additional Forex symbols are subscribed

- **WHEN** another downstream client requests a different Twelve Data-backed Forex symbol
- **THEN** the adapter reuses the existing Twelve Data WebSocket connection
- **AND** it sends a provider-symbol subscription update without opening another Twelve Data
  connection

#### Scenario: Final Forex interest disconnects

- **WHEN** no downstream client requires any Twelve Data Forex interest after the idle grace period
- **THEN** the adapter unsubscribes provider symbols and disconnects the Twelve Data WebSocket
- **AND** SDK threads and callbacks are not left running for that provider

### Requirement: Twelve Data price events produce Forex quote events

The Twelve Data Forex stream adapter SHALL normalize valid realtime price events into existing
provider-agnostic public quote events.

#### Scenario: Valid Forex price event is received

- **WHEN** Twelve Data emits a valid price event for a subscribed Forex provider symbol
- **THEN** the adapter emits one `StreamQuote` using the canonical symbol
- **AND** the downstream public event contains exactly `type`, `symbol`, `price`, and `receivedAt`

#### Scenario: Forex price event is malformed

- **WHEN** a Twelve Data WebSocket event is missing the subscribed symbol, has an invalid price, or
  has an unsupported event type
- **THEN** the adapter rejects the event without exposing the raw payload
- **AND** it does not update caches or fan out a downstream quote

### Requirement: YFINANCE streams use one shared asynchronous WebSocket

The gateway SHALL use yfinance `AsyncWebSocket` behind a repository-owned stream adapter and SHALL
maintain at most one process-local yfinance WebSocket connection for all active YFINANCE quote
interests.

#### Scenario: First YFINANCE interest is registered

- **WHEN** the first enabled YFINANCE quote interest is registered
- **THEN** the adapter creates one yfinance asynchronous WebSocket client lazily
- **AND** subscribes the persisted provider symbol on that connection
- **AND** starts one listener task

#### Scenario: Additional YFINANCE interests are registered

- **WHEN** additional quote interests reference YFINANCE provider symbols
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

### Requirement: Silent YFINANCE subscriptions remain connecting

The gateway SHALL treat a successful yfinance subscription as active even when Yahoo emits no
usable tick and SHALL NOT add polling, provider-symbol remapping, or cross-provider fallback.

#### Scenario: Subscribed YFINANCE symbol emits no tick

- **WHEN** yfinance accepts a provider-symbol subscription but no valid event has been observed
- **THEN** the downstream quote interest remains in `CONNECTING`
- **AND** the gateway emits no fabricated quote, stale, or provider-error event solely due
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

- **WHEN** no quote interest references a subscribed YFINANCE provider symbol
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

### Requirement: Twelve Data crypto streams use the shared upstream WebSocket

The gateway SHALL serve enabled `BTC/USD` and `ETH/USD` stream interests through the shared
Twelve Data WebSocket when those symbols are mapped to `TWELVE_DATA`.

#### Scenario: Crypto subscription is opened
- **WHEN** a client subscribes to `BTC/USD` or `ETH/USD`
- **THEN** quote interests use the persisted `TWELVE_DATA` mapping
- **AND** the Twelve Data stream adapter subscribes the matching provider symbol

### Requirement: Stream market values are independent of display precision

The gateway SHALL retain normalized WebSocket quote values internally, SHALL serialize quote prices
with `ROUND_HALF_UP` rounding and exact padding according to symbol `price_display_decimals`, and
SHALL not repeat display metadata in quote events.

#### Scenario: Stream quote exceeds display decimals

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** a normalized stream quote price is `Decimal("2934.5678")`
- **THEN** the quote event contains `"price":"2934.57"`
- **AND** it does not contain `priceDisplayDecimals`

#### Scenario: Stream price requires trailing-zero padding

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** a normalized stream price is `Decimal("2934.5")`
- **THEN** the corresponding public price field is `"2934.50"`

### Requirement: Quote stream request rejection is diagnostically observable

The gateway SHALL emit a structured warning for every rejected WebSocket request with the stable
operation name, request ID, error code, requested symbols, and submitted `timeframe` value when
that value is present. The log SHALL NOT include credentials, raw provider payloads, or stack
traces for client request-shape failures.

#### Scenario: Timeframe rejection is logged with safe context

- **WHEN** a client requests `WS /v1/stream?symbols=TSLA&timeframe=1w`
- **THEN** the gateway logs `websocket_request_rejected` with `operation: "stream.request"` and
  `error_code: "TIMEFRAME_NOT_ALLOWED"`
- **AND** the log includes the request ID, submitted symbols, and submitted timeframe
