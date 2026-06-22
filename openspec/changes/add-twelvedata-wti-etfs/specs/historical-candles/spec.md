## ADDED Requirements

### Requirement: WTI and ETF historical candles use the existing endpoint

The gateway SHALL serve enabled `WTI`, `SPY`, and `QQQ` through `GET /v1/candles` for every
supported public timeframe using their persisted `TWELVE_DATA` mappings.

#### Scenario: Missing WTI or ETF candle range is requested
- **WHEN** a valid WTI, SPY, or QQQ candle request contains eligible slots that are not available
  from persistence or the current-candle cache
- **THEN** the gateway requests only the missing eligible ranges from Twelve Data
- **AND** it normalizes, persists, caches, and returns candles through the existing public contract

#### Scenario: Requested range is fully cached
- **WHEN** every eligible requested candle is available from persistence or current cache
- **THEN** the gateway returns those candles without requiring a Twelve Data call

### Requirement: ETF candles use the regular US market session

The gateway SHALL treat ETF intraday candle slots as eligible Monday through Friday from 09:30
inclusive to 16:00 exclusive in `America/New_York`, and SHALL treat ETF daily candles as eligible
only for UTC date labels Monday through Friday.

#### Scenario: ETF intraday request spans regular-session boundaries
- **WHEN** a SPY or QQQ intraday request spans slots before 09:30, during 09:30 through 16:00, and
  at or after 16:00 New York time
- **THEN** only slots opening during the regular session count as expected candles
- **AND** closed-session slots are not requested, synthesized, returned, cached, or persisted

#### Scenario: ETF request crosses a daylight-saving transition
- **WHEN** the New York UTC offset changes between requested ETF sessions
- **THEN** session eligibility remains anchored to 09:30 and 16:00 local New York time

#### Scenario: ETF daily candle has a weekend label
- **WHEN** a provider, cache, or repository returns a SPY or QQQ daily candle labeled Saturday or
  Sunday in UTC
- **THEN** the gateway excludes that candle

### Requirement: WTI candles use the configured energy session

The gateway SHALL treat WTI intraday slots as eligible from Sunday 18:00 inclusive through Friday
17:00 exclusive in `America/New_York`, excluding the recurring 17:00 inclusive to 18:00 exclusive
maintenance window Monday through Thursday, and SHALL accept WTI daily candles only for UTC date
labels Monday through Friday.

#### Scenario: WTI request spans weekly close and reopen
- **WHEN** a WTI intraday request spans Friday 17:00 New York time through Sunday 18:00 New York
  time
- **THEN** closed-session slots do not count as missing candles
- **AND** the gateway does not request or synthesize those slots

#### Scenario: WTI request spans daily maintenance
- **WHEN** a WTI intraday request includes a Monday-through-Thursday slot opening from 17:00
  inclusive to 18:00 exclusive New York time
- **THEN** that slot is treated as market closed

#### Scenario: WTI session crosses a daylight-saving transition
- **WHEN** the New York UTC offset changes
- **THEN** WTI weekly and maintenance boundaries remain anchored to local New York time

### Requirement: Natural WTI and ETF provider gaps are preserved

The gateway MUST NOT synthesize missing WTI, SPY, or QQQ candles for eligible slots omitted by
Twelve Data.

#### Scenario: Provider returns a partial eligible range
- **WHEN** Twelve Data returns only some eligible WTI, SPY, or QQQ candles in a requested range
- **THEN** the gateway returns and persists the valid rows received
- **AND** it does not fabricate rows for omitted eligible slots
