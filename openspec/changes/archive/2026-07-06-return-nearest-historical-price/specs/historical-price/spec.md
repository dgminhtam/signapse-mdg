## MODIFIED Requirements

### Requirement: Historical price uses one-minute candle approximation
The gateway SHALL resolve historical price from the existing `1m` historical candle flow by finding
the nearest available eligible one-minute candle whose open time is at or before the containing
one-minute candle open for `at`.

#### Scenario: Timestamp resolves to containing one-minute bucket when available
- **WHEN** a client requests `at=2026-06-19T10:30:12Z`
- **AND** the eligible `2026-06-19T10:30:00Z` one-minute candle is available
- **THEN** the gateway resolves `pricedAt` as `2026-06-19T10:30:00Z`
- **AND** it returns that candle's close price

#### Scenario: Closed session resolves to previous eligible candle
- **WHEN** a client requests a past instant whose containing one-minute bucket is outside the
  symbol's market session
- **AND** a previous eligible one-minute candle is available
- **THEN** the gateway resolves `pricedAt` as the previous eligible candle open
- **AND** it returns that candle's close price

#### Scenario: Existing candle flow is reused
- **WHEN** the selected one-minute candle is absent from persistence
- **THEN** the gateway uses the existing historical candle provider-fill path for the symbol
- **AND** it applies the existing registry, provider routing, market-session, and gap behavior

### Requirement: Historical price response is minimal and provider-agnostic
A successful historical price response SHALL contain exactly `symbol`, `price`, and `pricedAt`.
`price` SHALL be the selected one-minute candle close serialized as a decimal string, and
`pricedAt` SHALL be the selected one-minute candle open serialized as an ISO-8601 UTC timestamp.

#### Scenario: Successful response fields are serialized
- **WHEN** the gateway finds a one-minute candle at or before the requested instant
- **THEN** the response contains exactly `symbol`, `price`, and `pricedAt`
- **AND** it does not contain timeframe, OHLC fields, volume, asset class, provider identity,
  provider symbol, freshness, or source metadata

#### Scenario: Decimal price is serialized as a string
- **WHEN** the selected candle close is returned
- **THEN** `price` is serialized as a fixed-point decimal string without binary floating-point
  conversion or scientific notation

#### Scenario: Priced timestamp may precede requested bucket
- **WHEN** the containing one-minute bucket for `at` has no eligible available candle
- **AND** the gateway finds an earlier eligible one-minute candle
- **THEN** `pricedAt` is earlier than the containing bucket open for `at`

### Requirement: Historical price failures use stable gateway errors
The endpoint SHALL return the standard gateway error envelope and SHALL NOT expose database
credentials, SQL, SDK exceptions, raw provider payloads, credentials, or stack traces.

#### Scenario: Symbol is unknown or disabled
- **WHEN** the requested canonical symbol is absent from the enabled registry
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `UNSUPPORTED_SYMBOL`

#### Scenario: Timestamp is missing or malformed
- **WHEN** `at` is missing, empty, invalid, or not explicitly UTC
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: No historical price is available before the requested instant
- **WHEN** the existing one-minute candle flow returns no eligible available candle at or before
  the requested instant
- **THEN** the gateway responds with HTTP status `404`
- **AND** the error code is `PRICE_NOT_FOUND`

#### Scenario: Persistence is unavailable
- **WHEN** registry or candle persistence cannot be queried or updated
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `DATABASE_UNAVAILABLE`

#### Scenario: Selected provider fails
- **WHEN** the selected candle provider fails while filling the selected one-minute candle lookup
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `PROVIDER_UNAVAILABLE`
