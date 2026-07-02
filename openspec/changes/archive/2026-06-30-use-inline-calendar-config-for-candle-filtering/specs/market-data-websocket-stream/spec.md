## ADDED Requirements

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
