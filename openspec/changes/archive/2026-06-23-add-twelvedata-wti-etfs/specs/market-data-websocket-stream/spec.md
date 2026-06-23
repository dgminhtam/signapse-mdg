## ADDED Requirements

### Requirement: WTI and ETF symbols use the shared Twelve Data stream

The gateway SHALL allow enabled WTI, SPY, and QQQ stream interests through the existing
`WS /v1/stream` endpoint and SHALL multiplex them on the shared process-local Twelve Data
WebSocket connection.

#### Scenario: New symbol stream subscription is opened
- **WHEN** a client subscribes to enabled `WTI`, `SPY`, or `QQQ`
- **THEN** the gateway registers quote and candle interests through the persisted `TWELVE_DATA`
  mapping
- **AND** it subscribes the matching provider symbol on the shared Twelve Data connection

#### Scenario: Mixed Twelve Data asset classes are subscribed
- **WHEN** downstream clients subscribe to Forex, WTI, and ETF symbols concurrently
- **THEN** the adapter reuses one process-local Twelve Data connection
- **AND** each normalized event uses the correct canonical symbol and persisted asset class

### Requirement: WTI and ETF price events produce normalized streams

The Twelve Data stream adapter SHALL normalize valid WTI, SPY, and QQQ price events into existing
quote events and SHALL derive candle events from accepted price ticks.

#### Scenario: Valid new-asset price event is received
- **WHEN** Twelve Data emits a valid price event for subscribed `WTI`, `SPY`, or `QQQ`
- **THEN** the gateway emits a quote containing exactly `type`, `symbol`, `price`, and `receivedAt`
- **AND** active candle interests receive provider-agnostic derived candle updates

#### Scenario: New-asset price event is malformed
- **WHEN** a WTI, SPY, or QQQ event has an unknown symbol, invalid event type, or non-positive
  non-finite price
- **THEN** the adapter discards the event without fanout
- **AND** it does not expose the raw provider payload

### Requirement: WTI and ETF stream candles follow market sessions

The gateway SHALL apply the same ETF regular-session and WTI energy-session policies used by
historical candles before emitting, caching, or persisting derived stream candles.

#### Scenario: ETF candle interest is outside regular hours
- **WHEN** a SPY or QQQ candle interest is active outside 09:30 through 16:00 New York time on a
  weekday or during a weekend
- **THEN** the candle channel reports `MARKET_CLOSED`
- **AND** valid quote events may continue independently
- **AND** no closed-session candle is emitted, cached, or persisted

#### Scenario: WTI candle interest is outside energy hours
- **WHEN** a WTI candle interest is active during the weekly closure or daily maintenance window
- **THEN** the candle channel reports `MARKET_CLOSED`
- **AND** valid quote events may continue independently
- **AND** no closed-session candle is emitted, cached, or persisted

#### Scenario: New-asset candle session reopens
- **WHEN** an active WTI, SPY, or QQQ candle interest transitions from closed to open session
- **THEN** the gateway reports the candle channel as `CONNECTING`
- **AND** the next accepted derived candle returns the channel to `SUBSCRIBED`
