## ADDED Requirements

### Requirement: Forex candles follow the Signapse weekly quote session

The gateway SHALL treat Forex candle slots as eligible only during the weekly quote session from
Sunday 17:00 inclusive through Friday 17:00 exclusive in `America/New_York`.

#### Scenario: Forex intraday candle opens before weekly close

- **WHEN** a `1m`, `5m`, `15m`, or `1h` Forex candle opens before Friday 17:00 New York time
- **THEN** it is eligible for normalization, persistence, and response inclusion

#### Scenario: Forex intraday candle opens at weekly close

- **WHEN** a Forex intraday candle opens exactly at Friday 17:00 New York time
- **THEN** it is excluded from normalization, persistence, cache merge, and response inclusion

#### Scenario: Forex intraday candle opens at weekly reopen

- **WHEN** a Forex intraday candle opens exactly at Sunday 17:00 New York time
- **THEN** it is eligible for normalization, persistence, and response inclusion

#### Scenario: Daylight-saving offset changes

- **WHEN** the New York UTC offset differs between summer and winter
- **THEN** the gateway preserves the same Sunday and Friday 17:00 New York wall-time boundaries
- **AND** it does not rely on a fixed UTC offset

### Requirement: Forex daily candles exclude weekend day labels

The gateway SHALL consider a `1d` Forex candle eligible when its UTC open-date label is Monday
through Friday and SHALL exclude UTC Saturday and Sunday labels.

#### Scenario: Weekday Forex daily candle is returned

- **WHEN** a valid Forex daily candle is labeled Monday through Friday in UTC
- **THEN** it remains eligible for persistence and response inclusion

#### Scenario: Weekend Forex daily candle is returned

- **WHEN** a provider or persistence returns a Forex daily candle labeled Saturday or Sunday in UTC
- **THEN** the candle is excluded and is not persisted or exposed

### Requirement: Weekly closed-session ranges do not trigger provider requests

The historical candle service SHALL calculate Forex missing ranges using only weekly-session
eligible slots.

#### Scenario: Request spans a closed weekend interval

- **WHEN** a Forex candle request spans open Friday slots, the weekly closed session, and open
  Sunday slots
- **THEN** the gateway splits provider fills into open-session ranges around the closed interval
- **AND** it makes no provider request for the closed interval

#### Scenario: Request contains only closed-session slots

- **WHEN** every requested Forex candle slot lies outside the weekly quote session
- **THEN** the gateway makes no provider candle request
- **AND** it returns a successful response with an empty `candles` array

#### Scenario: Non-Forex range spans the same weekend

- **WHEN** a non-Forex candle request spans Saturday and Sunday
- **THEN** the existing non-Forex gap calculation and provider behavior remain unchanged

### Requirement: Closed-session Forex candles are filtered at every data boundary

The gateway MUST exclude weekly closed-session Forex candles returned by providers, loaded from
persistence, or held as current in-memory candle state.

#### Scenario: Provider returns closed-session Forex candles

- **WHEN** a provider returns one or more Forex candles outside the weekly quote session
- **THEN** those candles are discarded
- **AND** they are not persisted or exposed

#### Scenario: PostgreSQL contains closed-session Forex candles

- **WHEN** a historical request loads previously persisted Forex candles outside the weekly quote
  session
- **THEN** those candles are excluded from the response
- **AND** they do not count as available open-session slots

#### Scenario: Current cache contains a closed-session Forex candle

- **WHEN** the current-candle cache contains a Forex candle outside the weekly quote session
- **THEN** that candle is not merged into the historical response

### Requirement: Existing closed-session Forex candles are removed

The deployment migration SHALL remove previously persisted Forex candles that violate the weekly
quote-session policy and SHALL leave non-Forex candles unchanged.

#### Scenario: Cleanup migration finds intraday weekend Forex candles

- **WHEN** the cleanup migration encounters an intraday `FOREX` candle opening from Friday 17:00
  inclusive through Sunday 17:00 exclusive in `America/New_York`
- **THEN** it deletes that candle

#### Scenario: Cleanup migration finds daily weekend Forex candles

- **WHEN** the cleanup migration encounters a `1d` `FOREX` candle labeled Saturday or Sunday in UTC
- **THEN** it deletes that candle

#### Scenario: Cleanup migration encounters non-Forex candles

- **WHEN** a candle belongs to any non-Forex asset class
- **THEN** the migration leaves it unchanged

#### Scenario: Cleanup migration is downgraded

- **WHEN** the cleanup migration downgrade runs
- **THEN** it completes without attempting to reconstruct deleted provider candles

## MODIFIED Requirements

### Requirement: Closed candles are reused from PostgreSQL

The gateway SHALL query persisted complete candles before calling the selected provider, SHALL
discard candles that violate the symbol's market-session policy, and SHALL identify missing
eligible timeframe slots within the requested range.

#### Scenario: Complete eligible range is persisted

- **WHEN** every eligible requested candle slot is available as a persisted complete candle
- **THEN** the gateway returns the persisted candles
- **AND** it makes no provider candle request

#### Scenario: Part of the eligible range is missing

- **WHEN** one or more contiguous eligible sections of the requested range are absent from
  persistence
- **THEN** the gateway requests only those missing eligible sections from the provider selected by
  the symbol's persisted mapping
- **AND** it merges valid fetched candles with eligible persisted candles by open time

#### Scenario: Provider omits an expected eligible slot

- **WHEN** the selected provider returns no candle for an expected eligible missing slot
- **THEN** the gateway returns the valid available candles after the fill attempt
- **AND** it does not synthesize an OHLCV candle

### Requirement: Only complete candles are persisted

The gateway SHALL determine completion from the candle close time and gateway receive time, SHALL
apply the symbol's market-session policy before persistence, SHALL upsert eligible complete candles
using `(provider, provider_symbol, timeframe, open_time)`, and MUST NOT persist a forming or
session-ineligible candle.

#### Scenario: Provider returns eligible closed candles

- **WHEN** fetched candles are market-session eligible and have close times earlier than the
  gateway receive time
- **THEN** they are returned with `complete=true`
- **AND** they are upserted idempotently into PostgreSQL

#### Scenario: Provider returns the current eligible forming candle

- **WHEN** a fetched market-session eligible candle has not closed at gateway receive time
- **THEN** it may be returned with `complete=false`
- **AND** it is not persisted

#### Scenario: Provider returns a session-ineligible candle

- **WHEN** a fetched candle violates the symbol's market-session policy
- **THEN** it is neither returned nor persisted

#### Scenario: Persisted and provider candles overlap

- **WHEN** an eligible fetched candle has the same identity as an eligible persisted complete
  candle
- **THEN** the persisted complete candle is retained in the response merge
- **AND** the response contains only one candle for that open time

### Requirement: Natural Forex market gaps are not synthesized

The gateway MUST preserve absent Twelve Data Forex candle slots during the open weekly quote
session as gaps and MUST NOT fabricate OHLCV candles for omitted provider data. Weekly
closed-session slots are not considered expected gaps.

#### Scenario: Provider returns no candles for an open-session range

- **WHEN** a valid Forex request covers eligible slots for which Twelve Data returns no rows
- **THEN** the gateway returns the valid available candles, which may be an empty list
- **AND** it does not create or persist synthetic candles

#### Scenario: Provider returns only part of an open-session Forex range

- **WHEN** Twelve Data omits one or more eligible slots but returns other valid rows
- **THEN** the gateway returns and persists only the valid eligible complete rows
- **AND** the omitted eligible slots remain absent

#### Scenario: Request includes weekly closed-session slots

- **WHEN** a Forex request includes slots outside the weekly quote session
- **THEN** those slots are excluded from expected-gap calculation
- **AND** the gateway does not synthesize or request candles for them
