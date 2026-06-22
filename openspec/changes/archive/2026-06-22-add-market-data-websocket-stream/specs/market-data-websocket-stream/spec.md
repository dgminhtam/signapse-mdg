## ADDED Requirements

### Requirement: Clients can subscribe to canonical real-time market data
The gateway SHALL expose `WS /v1/stream` with required comma-separated `symbols` and required
`timeframe` query parameters. A valid subscription SHALL include both quote and candle events for
each distinct requested canonical symbol.

#### Scenario: Valid multi-symbol subscription
- **WHEN** a client connects with enabled `BTC/USD,ETH/USD` symbols and timeframe `1m`
- **THEN** the gateway accepts one downstream WebSocket connection
- **AND** registers quote and `1m` candle interests for both symbols

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
- **AND** no Binance subscription is opened

#### Scenario: Too many symbols are requested
- **WHEN** the distinct symbol count exceeds `MAX_QUOTE_SYMBOLS`
- **THEN** the gateway closes the downstream connection with WebSocket code `1008`
- **AND** the close reason is `TOO_MANY_SYMBOLS`
- **AND** no Binance subscription is opened

#### Scenario: Any symbol is unknown or disabled
- **WHEN** one or more requested symbols have no enabled registry record
- **THEN** the complete subscription is rejected with WebSocket code `1008`
- **AND** the close reason is `UNSUPPORTED_SYMBOL`
- **AND** no partial upstream subscription is opened

#### Scenario: Timeframe is missing or unsupported
- **WHEN** `timeframe` is absent or is not one of `1m`, `5m`, `15m`, `1h`, or `1d`
- **THEN** the gateway closes the downstream connection with WebSocket code `1008`
- **AND** the close reason is `UNSUPPORTED_TIMEFRAME`
- **AND** no Binance subscription is opened

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
`code` and `message`. `channels` SHALL contain one or both of `quote` and `candle`.

#### Scenario: Valid connection begins upstream setup
- **WHEN** a validated downstream connection is registered but all required upstream streams have
  not produced valid data
- **THEN** the gateway emits `CONNECTING` for the requested symbols and channels

#### Scenario: All required streams become available
- **WHEN** every requested ticker and kline stream has produced at least one valid event
- **THEN** the gateway emits `SUBSCRIBED`

#### Scenario: One or more required streams become stale
- **WHEN** a required stream has produced no valid event for longer than
  `QUOTE_STALE_AFTER_SECONDS`
- **THEN** the gateway emits `STALE`
- **AND** `symbols` and `channels` identify the affected subscription interests

#### Scenario: Fresh data resumes after stale state
- **WHEN** every required stream for a downstream subscription is fresh again
- **THEN** the gateway emits `SUBSCRIBED` once for the recovered state

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
The stream manager SHALL maintain process-local reference counts for normalized upstream
interests, SHALL open an interest only for the first downstream consumer, and SHALL remove it only
after the final consumer leaves.

#### Scenario: Two clients request the same series
- **WHEN** two downstream clients subscribe to the same symbol and timeframe
- **THEN** they share one ticker interest and one kline interest upstream
- **AND** both clients receive matching normalized events

#### Scenario: One of multiple clients disconnects
- **WHEN** one client leaves while another still needs the same upstream interest
- **THEN** the upstream subscription remains active

#### Scenario: Final client disconnects
- **WHEN** the final client for an upstream interest disconnects
- **THEN** the manager unsubscribes that SDK stream after the configured idle grace period
- **AND** closes the SDK connection when no upstream interests remain

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
The gateway SHALL provide validated typed settings for Binance WebSocket base URL, SDK reconnect
delay, downstream queue capacity, upstream idle grace period, and freshness monitor interval.

#### Scenario: Stream settings are omitted
- **WHEN** stream-specific environment variables are absent
- **THEN** the gateway uses documented non-secret defaults suitable for the single-process MVP

#### Scenario: Invalid stream setting is supplied
- **WHEN** a queue capacity, reconnect delay, idle grace period, or monitor interval violates its
  numeric constraints
- **THEN** application configuration validation fails explicitly

