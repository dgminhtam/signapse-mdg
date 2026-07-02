## ADDED Requirements

### Requirement: Historical candles use inline calendar config for eligibility

The historical candle flow SHALL use each enabled symbol's inline calendar config to decide market
session eligibility when that config is present.

#### Scenario: Supported symbol calendar config is loaded

- **WHEN** an enabled symbol is resolved for a historical candle request
- **THEN** its internal symbol value includes `calendar_source`, `calendar_name`, and
  `calendar_timezone`

#### Scenario: Exchange intraday range includes closed slots

- **WHEN** a non-Forex symbol has `calendar_source` set to `pandas_market_calendars`
- **AND** a valid intraday candle request includes slots outside that calendar's open session
- **THEN** closed-session slots do not count as expected candles
- **AND** no provider request is made for closed-session-only sections

#### Scenario: Exchange break window is present

- **WHEN** a pandas calendar schedule contains `break_start` and `break_end`
- **AND** an intraday candle open falls inside the break window
- **THEN** that candle open is ineligible for provider fill, persistence, cache merge, and response
  inclusion

#### Scenario: Exchange daily label is closed

- **WHEN** a non-Forex pandas-calendar symbol has a `1d` candle labeled on a non-session UTC date
- **THEN** that candle is ineligible for provider fill, persistence, cache merge, and response
  inclusion

#### Scenario: Crypto symbol uses internal always-open config

- **WHEN** a symbol has `calendar_source=internal` and `calendar_name=24/7`
- **THEN** its candle eligibility remains always open

#### Scenario: Forex and XAU use the existing weekly quote session

- **WHEN** a Forex pair or spot `XAU/USD` is evaluated for candle eligibility
- **THEN** the existing Sunday 17:00 through Friday 17:00 New York weekly-session behavior is
  preserved

#### Scenario: Calendar config is absent or unsupported

- **WHEN** a supported symbol has no usable inline calendar config
- **THEN** the gateway falls back to the existing asset-class market-session policy
