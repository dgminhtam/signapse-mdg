## MODIFIED Requirements

### Requirement: Candle ranges use aligned half-open UTC semantics

The gateway SHALL interpret the requested range as exact half-open instants `[from, to)`, with
`from` inclusive and `to` exclusive. `from` MUST be a valid timezone-aware UTC timestamp. An
explicit `to` MUST be a valid timezone-aware UTC timestamp; when `to` is omitted, the gateway
SHALL resolve it to one captured request-time UTC instant. `from` MUST be earlier than the resolved
`to`. Public range boundaries are not required to align to timeframe or provider candle
boundaries.

#### Scenario: Boundary candles are selected
- **WHEN** a valid request covers `[from, to)`
- **THEN** a candle whose provider open time equals `from` is eligible for the response
- **AND** a candle whose provider open time equals `to` is excluded
- **AND** any candle whose provider open time falls strictly between the boundaries is eligible

#### Scenario: To parameter is omitted
- **WHEN** a valid candle request omits the `to` query parameter
- **THEN** the gateway captures the current UTC time once for that request
- **AND** it uses that instant as the exclusive range end for validation, provider access, and
  response serialization

#### Scenario: Explicit to parameter is empty
- **WHEN** a candle request includes an empty or whitespace-only `to` value
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Required range parameter is missing or malformed
- **WHEN** `from` is missing or either supplied boundary is not a valid explicitly UTC timestamp
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Time range is inverted or empty
- **WHEN** `from` is equal to or later than the resolved `to`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Time range boundaries are not timeframe-aligned
- **WHEN** valid UTC `from` or `to` values do not align to the requested timeframe
- **THEN** the gateway accepts the range
- **AND** it filters candles by their actual provider open times within `[from, to)`

### Requirement: Candle requests are bounded

The gateway SHALL reject a request that exceeds either `MAX_CANDLE_RANGE_DAYS` or
`MAX_CANDLES_PER_REQUEST`, with defaults of 30 days and 1,000 expected candles respectively.
Before symbol resolution, the gateway SHALL use the ceiling of elapsed duration divided by
timeframe duration as a conservative count bound. After symbol resolution, it SHALL enforce the
exact eligible count produced by the selected candle schedule.

#### Scenario: Elapsed range is too wide
- **WHEN** the difference between `from` and the resolved `to` exceeds `MAX_CANDLE_RANGE_DAYS`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Conservative candle count is too large
- **WHEN** the ceiling-based pre-validation count exceeds `MAX_CANDLES_PER_REQUEST`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Exact eligible candle count is too large
- **WHEN** the symbol's provider and market schedule produces more than
  `MAX_CANDLES_PER_REQUEST` eligible open times
- **THEN** the gateway responds with HTTP status `400`
- **AND** no provider candle request is made

### Requirement: Closed candles are reused from PostgreSQL

The gateway SHALL query persisted complete candles before calling the selected provider, SHALL
discard candles that violate the symbol's market-session policy, and SHALL identify missing
expected candle opens within the exact requested range using the symbol's selected candle
schedule.

#### Scenario: Complete eligible range is persisted
- **WHEN** every expected eligible candle open is available as a persisted complete candle
- **THEN** the gateway returns the persisted candles
- **AND** it makes no provider candle request

#### Scenario: Part of the eligible range is missing
- **WHEN** one or more expected eligible candle opens are absent from persistence
- **THEN** the gateway requests provider windows covering only those missing schedule sections
- **AND** it merges valid fetched candles with eligible persisted candles by actual open time

#### Scenario: Provider candle schedule is offset from UTC epoch
- **WHEN** a supported provider labels candles at an offset such as hourly `:30`
- **THEN** gap detection uses that provider/market schedule
- **AND** it does not repeatedly request the offset candle as though the epoch-aligned slot were
  missing

#### Scenario: Provider omits an expected eligible slot
- **WHEN** the selected provider returns no candle for an expected eligible missing slot
- **THEN** the gateway returns the valid available candles after the fill attempt
- **AND** it does not synthesize an OHLCV candle

## ADDED Requirements

### Requirement: Provider candle timestamps remain authoritative

The gateway MUST preserve valid provider candle open timestamps and MUST NOT shift them merely to
fit a universal epoch-aligned timeframe grid.

#### Scenario: Twelve Data returns an hourly candle at minute thirty
- **WHEN** Twelve Data returns a valid hourly candle with an open time such as `13:30Z`
- **THEN** the normalized candle retains `13:30Z` as its `openTime`
- **AND** its close time is derived from that actual open time and the requested duration

### Requirement: Twelve Data no-data ranges are successful empty results

The Twelve Data adapter SHALL distinguish a recognized valid no-data response for a requested time
series range from operational or contract failures.

#### Scenario: Provider reports no data for specified dates
- **WHEN** Twelve Data returns its recognized no-data condition for a valid time-series request
- **THEN** the adapter returns zero candles
- **AND** `GET /v1/candles` responds successfully with an empty `candles` array when no persisted or
  current candle is available

#### Scenario: Provider returns another error
- **WHEN** Twelve Data reports authentication, entitlement, rate-limit, invalid-parameter, unknown
  symbol, transport, timeout, or unrecognized error behavior
- **THEN** the adapter raises the sanitized provider-unavailable boundary
- **AND** no raw provider details are exposed
