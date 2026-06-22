## ADDED Requirements

### Requirement: Twelve Data adapter supports validated commodity and ETF instruments

The gateway SHALL use the official Twelve Data SDK behind a repository-owned provider adapter for
validated provider symbols `WTI`, `SPY`, and `QQQ`, and SHALL NOT expose SDK models, requests, raw
payloads, callbacks, threads, or exceptions outside the provider package.

#### Scenario: Validated instrument is requested
- **WHEN** the provider adapter receives `WTI`, `SPY`, or `QQQ`
- **THEN** it invokes the existing Twelve Data SDK operation using the matching provider symbol
- **AND** it returns repository-owned normalized domain models

#### Scenario: Instrument is outside the repository allowlist
- **WHEN** the provider adapter receives a Twelve Data provider symbol that is not explicitly
  supported
- **THEN** it does not issue a provider request for that symbol
- **AND** it reports the symbol as unavailable through the existing provider boundary

### Requirement: Twelve Data adapter terminology is asset-neutral

The Twelve Data adapter boundary SHALL use asset-neutral runtime names because one implementation
serves Forex, metals, US stocks, commodities, and ETFs.

#### Scenario: Application providers are wired
- **WHEN** the application builds REST and WebSocket providers for `TWELVE_DATA`
- **THEN** the provider types and factories do not imply that only Forex instruments are supported
- **AND** existing supported Twelve Data symbols retain their behavior

### Requirement: Twelve Data volume normalization is asset-aware

The Twelve Data candle adapter SHALL preserve valid provider volume when supplied and SHALL use
decimal zero only when volume is absent or null for an instrument whose upstream volume is
unavailable.

#### Scenario: ETF candle includes volume
- **WHEN** Twelve Data returns a valid SPY or QQQ candle with non-negative finite volume
- **THEN** the normalized candle preserves that exact decimal volume

#### Scenario: WTI candle omits volume
- **WHEN** Twelve Data returns a valid WTI candle with omitted or null volume
- **THEN** the normalized candle uses exact decimal zero

#### Scenario: Supplied volume is malformed
- **WHEN** any supported Twelve Data candle contains malformed, negative, or non-finite volume
- **THEN** the adapter rejects the provider payload through the sanitized provider error boundary
