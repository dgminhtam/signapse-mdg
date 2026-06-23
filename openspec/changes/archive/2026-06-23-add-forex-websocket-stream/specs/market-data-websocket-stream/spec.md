## ADDED Requirements

### Requirement: Stream interests are routed by persisted provider mapping

The gateway SHALL route each validated stream interest to the stream provider selected by the
enabled symbol's persisted `provider` and `provider_symbol` mapping.

#### Scenario: Mixed crypto and Forex subscription is accepted

- **WHEN** a client subscribes to enabled Binance-backed crypto symbols and Twelve Data-backed Forex
  symbols in one `/v1/stream` request
- **THEN** the gateway registers quote and candle interests for every requested canonical symbol
- **AND** it routes each upstream interest through that symbol's persisted provider mapping

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

## MODIFIED Requirements

### Requirement: Clients can subscribe to canonical real-time market data

The gateway SHALL expose `WS /v1/stream` with required comma-separated `symbols` and required
`timeframe` query parameters. A valid subscription SHALL include both quote and candle events for
each distinct requested canonical symbol, including enabled crypto and Forex symbols.

#### Scenario: Valid multi-symbol subscription
- **WHEN** a client connects with enabled `BTC/USD,ETH/USD` symbols and timeframe `1m`
- **THEN** the gateway accepts one downstream WebSocket connection
- **AND** registers quote and `1m` candle interests for both symbols

#### Scenario: Valid mixed-provider subscription
- **WHEN** a client connects with enabled `BTC/USD,EUR/USD` symbols and timeframe `1m`
- **THEN** the gateway accepts one downstream WebSocket connection
- **AND** registers quote and `1m` candle interests for both symbols
- **AND** routes the crypto interests to Binance and the Forex interests to Twelve Data

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
- **WHEN** `timeframe` is absent or is not one of `1m`, `5m`, `15m`, `1h`, or `1d`
- **THEN** the gateway closes the downstream connection with WebSocket code `1008`
- **AND** the close reason is `UNSUPPORTED_TIMEFRAME`
- **AND** no provider subscription is opened

#### Scenario: Registry validation is unavailable
- **WHEN** PostgreSQL cannot validate the requested symbols
- **THEN** the gateway closes the downstream connection with WebSocket code `1011`
- **AND** the close reason is `DATABASE_UNAVAILABLE`
- **AND** no database detail or credential is exposed

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
