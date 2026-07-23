## MODIFIED Requirements

### Requirement: Initial candle timeframes are explicitly supported

The gateway SHALL support public timeframes `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`, and
`1mo` and SHALL map them to the corresponding interval inside the selected provider adapter
boundary.

#### Scenario: Supported fixed-duration timeframe is requested

- **WHEN** a client requests `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, or `1w`
- **THEN** the gateway resolves the corresponding interval for the symbol's persisted provider

#### Scenario: Supported monthly timeframe is requested

- **WHEN** a client requests `1mo`
- **THEN** the gateway resolves the corresponding monthly interval for the symbol's persisted
  provider
- **AND** monthly candle opens and closes are calculated using calendar months rather than a fixed
  day count

#### Scenario: Unsupported timeframe is requested

- **WHEN** a client requests any other timeframe, including `h4`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `UNSUPPORTED_TIMEFRAME`
- **AND** the sanitized error details identify the rejected timeframe

### Requirement: Forex candles follow the Signapse weekly quote session

The gateway SHALL treat Forex candle slots as eligible only during the weekly quote session from
Sunday 17:00 inclusive through Friday 17:00 exclusive in `America/New_York`.

#### Scenario: Forex intraday candle opens before weekly close

- **WHEN** a `1m`, `5m`, `15m`, `30m`, `1h`, or `4h` Forex candle opens before Friday 17:00 New
  York time
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
