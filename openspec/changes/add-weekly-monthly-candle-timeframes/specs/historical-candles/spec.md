## MODIFIED Requirements

### Requirement: Initial candle timeframes are explicitly supported

The gateway SHALL support public timeframes `1m`, `5m`, `15m`, `30m`, `1h`, `1d`, `1w`, and
`1mo` and SHALL map them to the corresponding interval inside the selected provider adapter
boundary.

#### Scenario: Supported fixed-duration timeframe is requested

- **WHEN** a client requests `1m`, `5m`, `15m`, `30m`, `1h`, `1d`, or `1w`
- **THEN** the gateway resolves the corresponding interval for the symbol's persisted provider

#### Scenario: Supported monthly timeframe is requested

- **WHEN** a client requests `1mo`
- **THEN** the gateway resolves the corresponding monthly interval for the symbol's persisted
  provider
- **AND** monthly candle opens and closes are calculated using calendar months rather than a fixed
  day count

#### Scenario: Unsupported timeframe is requested

- **WHEN** a client requests any other timeframe
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `UNSUPPORTED_TIMEFRAME`
- **AND** the sanitized error details identify the rejected timeframe

### Requirement: Candle requests are bounded
The gateway SHALL reject a request that exceeds `MAX_CANDLES_PER_REQUEST`, with a default of
1,000 expected candles. Pre-validation SHALL use a conservative expected-count bound for the
requested timeframe; after symbol resolution the exact provider/market schedule count SHALL also
be enforced.

#### Scenario: Expected candle count is too large
- **WHEN** either the conservative or exact scheduled count exceeds `MAX_CANDLES_PER_REQUEST`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Monthly range is counted by calendar opens
- **WHEN** a `1mo` request spans calendar-month candle opens
- **THEN** the exact scheduled count is based on eligible monthly open timestamps inside
  `[from,to)`
- **AND** no fixed 30-day duration is used to accept, reject, or fetch monthly candles
