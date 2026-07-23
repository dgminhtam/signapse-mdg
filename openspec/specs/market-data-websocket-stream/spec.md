# Market Data WebSocket Stream Specification

## Purpose

Define the provider-agnostic real-time market data WebSocket contract, validation, upstream
subscription sharing, fanout, cache integration, persistence handoff, and lifecycle behavior.
## Requirements
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
### Requirement: The complete subscription is validated before provider access

The gateway MUST validate request shape, the configured distinct-symbol limit, every symbol
against the enabled PostgreSQL registry, and the timeframe against the supported timeframe map
before opening or extending an upstream subscription.

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
- **AND** no partial upstream subscription is opened

#### Scenario: Timeframe is missing or unsupported
- **WHEN** `timeframe` is absent or is not one of `1m`, `5m`, `15m`, `1h`, `4h`, or `1d`
- **THEN** the gateway closes the downstream connection with WebSocket code `1008`
- **AND** the close reason is `UNSUPPORTED_TIMEFRAME`
- **AND** no provider subscription is opened

#### Scenario: Registry validation is unavailable
- **WHEN** PostgreSQL cannot validate the requested symbols
- **THEN** the gateway closes the downstream connection with WebSocket code `1011`
- **AND** the close reason is `DATABASE_UNAVAILABLE`
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

### Requirement: Public candle events are minimal and provider-agnostic
Each public candle event SHALL contain exactly `type`, `symbol`, `timeframe`, `openTime`,
`closeTime`, `open`, `high`, `low`, `close`, `volume`, `complete`, and `receivedAt`. `type` SHALL
be `candle`, OHLCV values SHALL be fixed-point decimal strings, and timestamps SHALL be UTC.

#### Scenario: Forming kline update is received
- **WHEN** Binance sends a valid subscribed kline update whose closed flag is false
- **THEN** the gateway emits a candle event with `complete=false`
- **AND** the event contains no asset class, provider identity, or provider symbol

#### Scenario: Closing kline update is received
- **WHEN** Binance sends a valid subscribed kline update whose closed flag is true
- **THEN** the gateway emits a candle event with `complete=true`
- **AND** its open and close times match the normalized timeframe window

#### Scenario: Candle volume is zero with scale
- **WHEN** candle volume is represented internally as a Decimal such as `0E-8`
- **THEN** the public volume is serialized as fixed-point `0.00000000`
- **AND** no scientific notation is emitted

### Requirement: Status events describe downstream stream lifecycle

The gateway SHALL emit provider-agnostic status events containing exactly `type`, `state`,
`symbols`, `channels`, and `observedAt`, except that an `ERROR` event SHALL additionally contain
`code` and `message`. `channels` SHALL contain one or both of `quote` and `candle`. Supported
states SHALL include `CONNECTING`, `SUBSCRIBED`, `STALE`, `RECONNECTING`, `MARKET_CLOSED`, and
`ERROR`.

#### Scenario: Valid connection begins upstream setup
- **WHEN** a validated downstream connection is registered but all required open-session upstream
  streams have not produced valid data
- **THEN** the gateway emits `CONNECTING` for the requested symbols and channels

#### Scenario: All required streams become available
- **WHEN** every requested open-session ticker and candle stream has produced at least one valid
  event
- **THEN** the gateway emits `SUBSCRIBED`

#### Scenario: One or more required streams become stale
- **WHEN** a required open-session stream has produced no valid event for longer than
  `QUOTE_STALE_AFTER_SECONDS`
- **THEN** the gateway emits `STALE`
- **AND** `symbols` and `channels` identify the affected subscription interests

#### Scenario: Fresh data resumes after stale state
- **WHEN** every required open-session stream for a downstream subscription is fresh again
- **THEN** the gateway emits `SUBSCRIBED` once for the recovered state

#### Scenario: Forex candle channel is outside market session
- **WHEN** a Forex candle interest is outside the Signapse weekly quote session
- **THEN** the gateway emits `MARKET_CLOSED`
- **AND** `symbols` and `channels` identify the closed Forex candle interest
- **AND** the closed candle interest is not reported as `STALE`

#### Scenario: Forex candle channel reopens
- **WHEN** a Forex candle interest transitions from closed session to open session
- **THEN** the gateway emits `CONNECTING` for that candle channel until a valid derived candle event
  is produced

#### Scenario: Upstream reconnect is observed
- **WHEN** the provider adapter detects connection loss or an SDK reconnect cycle
- **THEN** affected downstream clients receive `RECONNECTING`
- **AND** subscriptions remain registered for automatic resubscription

#### Scenario: Stream cannot continue
- **WHEN** an unrecoverable provider or stream-manager failure prevents serving a registered
  subscription
- **THEN** the gateway emits `ERROR` with sanitized `PROVIDER_UNAVAILABLE` code and message
- **AND** closes the downstream connection with WebSocket code `1011`

### Requirement: Binance streams use the official SDK behind an adapter
The Binance adapter SHALL use the official Spot SDK WebSocket Streams API for individual-symbol
ticker and UTC kline streams and MUST isolate all SDK models, callbacks, handles, exceptions, and
provider naming inside the provider boundary.

#### Scenario: First subscription needs Binance streams
- **WHEN** a requested quote or candle interest has no active upstream subscription
- **THEN** the adapter creates an SDK WebSocket stream connection if needed
- **AND** subscribes to lowercase `<provider-symbol>@ticker` and
  `<provider-symbol>@kline_<interval>` streams through SDK operations

#### Scenario: SDK callback receives valid ticker data
- **WHEN** the SDK invokes a ticker callback
- **THEN** the adapter validates the provider symbol, event time, and latest price
- **AND** enqueues a repository-owned normalized quote event without awaiting downstream I/O

#### Scenario: SDK callback receives valid kline data
- **WHEN** the SDK invokes a kline callback
- **THEN** the adapter validates symbol, interval, timestamps, OHLCV values, and completion state
- **AND** enqueues a repository-owned normalized candle event without awaiting downstream I/O

#### Scenario: Provider payload is malformed
- **WHEN** an SDK callback contains missing, non-finite, inconsistent, duplicate, or unexpected
  data
- **THEN** the adapter rejects that event without exposing the payload to clients
- **AND** records a sanitized provider error

### Requirement: Matching upstream subscriptions are shared and lazy

The stream manager and provider router SHALL maintain process-local reference counts for normalized
upstream interests, SHALL open an interest only for the first downstream consumer, and SHALL remove
it only after the final consumer leaves.

#### Scenario: Two clients request the same series
- **WHEN** two downstream clients subscribe to the same symbol and timeframe
- **THEN** they share one quote interest and one candle interest upstream
- **AND** both clients receive matching normalized events

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

The adapter SHALL normalize valid WTI, SPY, and QQQ prices and derive candle events.

#### Scenario: Valid price event is received
- **WHEN** Twelve Data emits a valid event for a subscribed new asset
- **THEN** existing provider-agnostic quote and candle shapes are emitted

### Requirement: WTI and ETF stream candles follow market sessions

The gateway SHALL apply ETF and WTI session policies before emitting, caching, or persisting
derived candles.

#### Scenario: New asset candle interest is closed
- **WHEN** a WTI or ETF candle interest is outside its configured session
- **THEN** its candle channel reports `MARKET_CLOSED`

#### Scenario: New asset candle session reopens
- **WHEN** the configured session reopens
- **THEN** the candle channel transitions through `CONNECTING` to `SUBSCRIBED`

### Requirement: Stream candle sessions use inline calendar config

The WebSocket stream flow SHALL use each enabled symbol's inline calendar config to decide candle
session eligibility and market-closed status when that config is present.

#### Scenario: Stream symbol calendar config is loaded

- **WHEN** enabled symbols are loaded for a stream subscription
- **THEN** their internal symbol values include `calendar_source`, `calendar_name`, and
  `calendar_timezone`

#### Scenario: Derived exchange candle is outside session

- **WHEN** a valid price tick maps to a candle bucket outside a non-Forex symbol's pandas calendar
  session
- **THEN** no derived candle event is emitted for that bucket
- **AND** no ineligible stream candle is cached or persisted

#### Scenario: Derived exchange candle is inside break window

- **WHEN** a valid price tick maps to a candle bucket inside a pandas calendar break window
- **THEN** no derived candle event is emitted for that bucket
- **AND** no ineligible stream candle is cached or persisted

#### Scenario: Exchange candle channel is closed

- **WHEN** a candle stream interest is outside its inline calendar-config session
- **THEN** the gateway emits `MARKET_CLOSED` for that candle interest
- **AND** the closed candle interest is not reported as `STALE`

#### Scenario: Exchange candle channel reopens

- **WHEN** a candle stream interest transitions from closed to open under its inline calendar config
- **THEN** the gateway emits `CONNECTING` for that candle channel until a valid candle event is
  produced

#### Scenario: Forex stream behavior remains weekly-session based

- **WHEN** a Forex pair or spot `XAU/USD` stream candle is evaluated for session eligibility
- **THEN** the existing Sunday 17:00 through Friday 17:00 New York weekly-session behavior is
  preserved

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
### Requirement: Twelve Data Forex streams use one shared upstream WebSocket

The Twelve Data Forex stream adapter SHALL use the official `twelvedata` SDK WebSocket object
behind the provider boundary and SHALL maintain at most one process-local Twelve Data WebSocket
connection for all active Forex stream interests.

#### Scenario: First Forex subscription opens Twelve Data WebSocket

- **WHEN** the first Twelve Data-backed Forex quote or candle interest is registered
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

### Requirement: Twelve Data price events derive Forex candle events

The gateway SHALL derive Forex candle events from accepted Twelve Data realtime price events for
supported public timeframes.

#### Scenario: First tick creates a forming Forex candle

- **WHEN** the adapter receives the first valid price tick for a subscribed Forex candle timeframe
- **THEN** it creates a candle bucket aligned to that timeframe's UTC open time
- **AND** it emits a `complete=false` candle with `open`, `high`, `low`, and `close` equal to the
  tick price
- **AND** it sets `volume` to decimal zero

#### Scenario: Later tick updates the current bucket

- **WHEN** another valid price tick lands in the same Forex candle bucket
- **THEN** the adapter updates `high`, `low`, and `close` from the tick price
- **AND** it emits a new `complete=false` candle event for that bucket

#### Scenario: Tick advances to a later bucket

- **WHEN** a valid price tick lands after the current Forex candle bucket
- **THEN** the adapter emits the previous bucket as `complete=true`
- **AND** it starts and emits the new bucket as `complete=false`
- **AND** it does not synthesize skipped buckets without price ticks

### Requirement: Forex stream candles follow market-session policy

The gateway SHALL generate, cache, fan out, and persist Forex stream candle events only when their
bucket open time is eligible under the symbol's market-session policy.

#### Scenario: Forex tick arrives during open weekly session

- **WHEN** a valid Twelve Data price tick maps to a Forex candle bucket inside the weekly quote
  session
- **THEN** the derived candle is eligible for downstream fanout and cache updates

#### Scenario: Forex tick maps to closed weekly session

- **WHEN** a valid Twelve Data price tick maps to a Forex candle bucket outside the weekly quote
  session
- **THEN** no Forex candle event is emitted for that bucket
- **AND** no ineligible stream candle is cached or persisted

#### Scenario: Forex daily stream candle is labeled on a weekend

- **WHEN** a derived Forex `1d` stream candle bucket has a UTC Saturday or Sunday open-date label
- **THEN** that candle bucket is excluded from downstream fanout, cache updates, and persistence

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
`1h`, `4h`, and `1d` interests and SHALL use decimal zero volume.

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

### Requirement: Twelve Data crypto streams use the shared upstream WebSocket

The gateway SHALL serve enabled `BTC/USD` and `ETH/USD` stream interests through the shared
Twelve Data WebSocket when those symbols are mapped to `TWELVE_DATA`.

#### Scenario: Crypto subscription is opened
- **WHEN** a client subscribes to `BTC/USD` or `ETH/USD`
- **THEN** quote and candle interests use the persisted `TWELVE_DATA` mapping
- **AND** the Twelve Data stream adapter subscribes the matching provider symbol
