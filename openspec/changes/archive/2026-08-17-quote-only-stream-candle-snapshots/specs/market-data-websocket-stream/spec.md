# Market Data WebSocket Stream Specification Delta

## MODIFIED Requirements

### Requirement: Clients can subscribe to canonical real-time market data

The gateway SHALL expose `WS /v1/stream` with required comma-separated `symbols` and at most one
optional case-sensitive `provider` query value. The request SHALL NOT include `timeframe`. A valid
subscription SHALL deliver quote events only for each distinct requested canonical symbol, and one
Provider Override SHALL apply to every symbol in the subscription.

#### Scenario: Valid multi-symbol default subscription

- **WHEN** a client connects with enabled `BTC/USD,ETH/USD` symbols without `provider` or
  `timeframe`
- **THEN** the gateway accepts one downstream WebSocket connection
- **AND** registers one quote interest per symbol through each symbol's Default Provider
- **AND** emits lifecycle status events with `channels: ["quote"]`

#### Scenario: Valid mixed-catalog default subscription

- **WHEN** a client connects with enabled `BTC/USD,EUR/USD` symbols without `provider` or
  `timeframe`
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

- **WHEN** every requested symbol is enabled but one or more lack a Provider Mapping matching the
  override
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

- **WHEN** PostgreSQL cannot validate the requested symbols or an enabled asset has no Default
  Provider
- **THEN** the gateway closes the downstream connection with WebSocket code `1011`
- **AND** the close reason is `DATABASE_UNAVAILABLE`
- **AND** an explicit Provider Override does not bypass an invalid registry state
- **AND** no database detail or credential is exposed

### Requirement: Status events describe downstream stream lifecycle

The gateway SHALL emit provider-agnostic status events containing exactly `type`, `state`,
`symbols`, `channels`, and `observedAt`, except that an `ERROR` event SHALL additionally contain
`code` and `message`. For this quote-only stream, `channels` SHALL always be exactly `["quote"]`.
Supported states SHALL include `CONNECTING`, `SUBSCRIBED`, `STALE`, `RECONNECTING`, and `ERROR`;
the gateway SHALL NOT emit `MARKET_CLOSED`.

#### Scenario: Valid connection begins upstream setup

- **WHEN** a validated downstream connection is registered but no valid quote has been received
- **THEN** the gateway emits `CONNECTING` for the requested symbols and `channels: ["quote"]`

#### Scenario: First valid quote becomes available

- **WHEN** the first valid normalized quote is received for a registered quote subscription
- **THEN** the gateway emits `SUBSCRIBED` for the requested symbols and `channels: ["quote"]`

#### Scenario: Quote stream becomes stale

- **WHEN** no valid quote has been received for longer than `QUOTE_STALE_AFTER_SECONDS`
- **THEN** the gateway emits `STALE`
- **AND** `symbols` and `channels` identify the quote-only subscription

#### Scenario: Fresh data resumes after stale state

- **WHEN** a new valid quote is received after the subscription was stale
- **THEN** the gateway emits `SUBSCRIBED` once for the recovered state

#### Scenario: Upstream reconnect is observed

- **WHEN** the provider adapter detects connection loss or an SDK reconnect cycle
- **THEN** affected downstream clients receive `RECONNECTING`
- **AND** quote subscriptions remain registered for automatic resubscription

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

- **WHEN** one client leaves while another still needs the same upstream quote interest
- **THEN** the upstream subscription remains active

#### Scenario: Final client disconnects

- **WHEN** the final client for an upstream quote interest disconnects
- **THEN** the manager unsubscribes that provider stream after the configured idle grace period
- **AND** closes the provider connection when no upstream quote interests for that provider remain

### Requirement: WTI and ETF price events produce normalized streams

The adapter SHALL normalize valid WTI, SPY, and QQQ prices into the existing provider-agnostic
quote event shape. It SHALL NOT derive or emit WebSocket candle events.

#### Scenario: Valid price event is received

- **WHEN** Twelve Data emits a valid event for a subscribed WTI or ETF provider symbol
- **THEN** the adapter emits the normalized quote event for the canonical symbol
- **AND** no candle interest, candle event, cache update, or persistence handoff is created

### Requirement: Stream interests are routed by persisted provider mapping

The gateway SHALL route every validated quote stream interest through the immutable Provider
Selection resolved from the enabled canonical symbol's normalized mappings. When `provider` is
omitted it MUST use the Default Provider; when supplied it MUST use the exact configured mapping
regardless of default state. It MUST NOT automatically fall back.

#### Scenario: Mixed-provider default subscription is accepted

- **WHEN** a client omits Provider Override and subscribes to enabled symbols with different
  Default Providers
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

- **WHEN** a configured Provider Mapping has no usable quote stream adapter or cannot establish
  its upstream subscription
- **THEN** the gateway closes the downstream connection with WebSocket code `1011`
- **AND** the close reason is `PROVIDER_UNAVAILABLE`
- **AND** it does not fall back to another Provider Mapping

#### Scenario: Provider failure is isolated to affected interests

- **WHEN** one upstream provider emits an error signal for its active quote interests
- **THEN** downstream status events identify only the affected symbols and `channels: ["quote"]`
- **AND** unaffected provider interests can continue receiving normalized quote events

### Requirement: Twelve Data Forex streams use one shared upstream WebSocket

The Twelve Data Forex stream adapter SHALL use the official `twelvedata` SDK WebSocket object
behind the provider boundary and SHALL maintain at most one process-local Twelve Data WebSocket
connection for all active Forex quote interests.

#### Scenario: First Forex quote subscription opens Twelve Data WebSocket

- **WHEN** the first Twelve Data-backed Forex quote interest is registered
- **THEN** the adapter creates and connects one SDK WebSocket object
- **AND** it subscribes the required provider symbol on that connection

#### Scenario: Additional Forex symbols are subscribed

- **WHEN** another downstream client requests a different Twelve Data-backed Forex symbol
- **THEN** the adapter reuses the existing Twelve Data WebSocket connection
- **AND** it sends a provider-symbol subscription update without opening another Twelve Data
  connection

#### Scenario: Final Forex quote interest disconnects

- **WHEN** no downstream client requires any Twelve Data Forex quote interest after the idle grace
  period
- **THEN** the adapter unsubscribes provider symbols and disconnects the Twelve Data WebSocket
- **AND** SDK threads and callbacks are not left running for that provider

### Requirement: YFINANCE streams use one shared asynchronous WebSocket

The gateway SHALL use yfinance `AsyncWebSocket` behind a repository-owned stream adapter and SHALL
maintain at most one process-local yfinance WebSocket connection for all active YFINANCE quote
interests.

#### Scenario: First YFINANCE quote interest is registered

- **WHEN** the first enabled YFINANCE quote interest is registered
- **THEN** the adapter creates one yfinance asynchronous WebSocket client lazily
- **AND** subscribes the persisted provider symbol on that connection
- **AND** starts one listener task

#### Scenario: Additional YFINANCE quote interests are registered

- **WHEN** additional quote interests reference YFINANCE provider symbols
- **THEN** the adapter reuses the existing WebSocket connection
- **AND** subscribes each provider symbol at most once while it has active references

#### Scenario: Application starts without YFINANCE stream clients

- **WHEN** the application starts and no downstream client requests a YFINANCE asset
- **THEN** no yfinance WebSocket client, connection, subscription, or listener task is created

### Requirement: Silent YFINANCE subscriptions remain connecting

The gateway SHALL treat a successful yfinance quote subscription as active even when Yahoo emits
no usable tick and SHALL NOT add polling, provider-symbol remapping, or cross-provider fallback.

#### Scenario: Subscribed YFINANCE symbol emits no tick

- **WHEN** yfinance accepts a provider-symbol subscription but no valid quote event has been
  observed
- **THEN** the downstream quote interest remains in `CONNECTING`
- **AND** the gateway emits no fabricated quote, stale, or provider-error event solely due to the
  absence of a first tick

#### Scenario: Previously active YFINANCE interest stops receiving ticks

- **WHEN** a YFINANCE quote interest has emitted valid data and later exceeds the configured
  freshness threshold
- **THEN** existing stream freshness behavior can report that interest as `STALE`
- **AND** no fallback provider is selected

### Requirement: YFINANCE stream lifecycle is supervised and deterministic

The yfinance stream adapter SHALL own listener supervision, active quote-interest resubscription,
unsubscribe behavior, and final shutdown without leaving background tasks running.

#### Scenario: Listener terminates while interests remain

- **WHEN** the yfinance listener raises or returns while active quote interests remain
- **THEN** the adapter emits `RECONNECTING` for its active quote interests
- **AND** creates a fresh client after the configured reconnect delay
- **AND** resubscribes the current provider-symbol set before resuming listening

#### Scenario: Final reference to a provider symbol is removed

- **WHEN** no quote interest references a subscribed YFINANCE provider symbol
- **THEN** the adapter unsubscribes that provider symbol
- **AND** leaves other active YFINANCE symbols subscribed

#### Scenario: Final YFINANCE interest is removed

- **WHEN** no YFINANCE quote interest remains
- **THEN** the adapter cancels and awaits its listener supervision
- **AND** closes the yfinance WebSocket connection

#### Scenario: Application shuts down with active YFINANCE interests

- **WHEN** FastAPI lifespan shutdown begins
- **THEN** yfinance subscriptions, listener tasks, and WebSocket resources are closed
  deterministically
- **AND** shutdown leaves no unhandled task exception

### Requirement: Twelve Data crypto streams use the shared upstream WebSocket

The gateway SHALL serve enabled `BTC/USD` and `ETH/USD` quote interests through the shared Twelve
Data WebSocket when those symbols are mapped to `TWELVE_DATA`.

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

## REMOVED Requirements

### Requirement: Public candle events are minimal and provider-agnostic

**Reason**: The WebSocket no longer exposes candle events; candle snapshots are served by
`GET /v1/candles`.

**Migration**: Candle consumers must call `GET /v1/candles` with an explicit `timeframe` and use
the unchanged candle response shape, including `complete=false` for a forming snapshot.

### Requirement: WTI and ETF stream candles follow market sessions

**Reason**: WTI and ETF WebSocket candle interests and derived candle events are removed.

**Migration**: Request WTI and ETF candles through `GET /v1/candles`.

### Requirement: Stream candle sessions use inline calendar config

**Reason**: The live stream no longer evaluates candle session eligibility.

**Migration**: Keep session/calendar eligibility in the REST candle service and provider fill path.

### Requirement: Twelve Data price events derive Forex candle events

**Reason**: Quote ticks are no longer aggregated into WebSocket candles.

**Migration**: Use the existing Twelve Data-backed `GET /v1/candles` operation for Forex candle
snapshots.

### Requirement: Forex stream candles follow market-session policy

**Reason**: There are no Forex WebSocket candle events to gate, cache, fan out, or persist.

**Migration**: Apply the existing weekly-session policy in the REST candle service.

### Requirement: YFINANCE price ticks derive candle events

**Reason**: YFINANCE quote ticks are no longer aggregated into WebSocket candles.

**Migration**: Use the existing YFINANCE-backed `GET /v1/candles` operation for candle snapshots.
