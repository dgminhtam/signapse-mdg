## ADDED Requirements

### Requirement: Historical price can be requested by canonical symbol and instant
The gateway SHALL expose `GET /v1/historical-price` for one canonical `symbol` and one UTC `at`
timestamp, and SHALL NOT require or accept a public timeframe parameter for this lookup.

#### Scenario: Valid historical price request
- **WHEN** a client requests an enabled canonical symbol and valid UTC `at` timestamp
- **THEN** the gateway responds with HTTP status `200`
- **AND** the response represents that canonical symbol

#### Scenario: Timeframe is not part of the public contract
- **WHEN** a client requests historical price
- **THEN** the client supplies no timeframe value
- **AND** the gateway uses its internal historical-price resolution policy

### Requirement: Historical price uses one-minute candle approximation
The gateway SHALL resolve historical price from the existing `1m` historical candle flow by flooring
`at` to the containing one-minute candle open and requesting the half-open range
`[pricedAt, pricedAt + 1 minute)`.

#### Scenario: Timestamp is floored to one-minute bucket
- **WHEN** a client requests `at=2026-06-19T10:30:12Z`
- **THEN** the gateway resolves `pricedAt` as `2026-06-19T10:30:00Z`
- **AND** it looks up the one-minute candle containing the requested instant

#### Scenario: Existing candle flow is reused
- **WHEN** the one-minute candle is absent from persistence
- **THEN** the gateway uses the existing historical candle provider-fill path for the symbol
- **AND** it applies the existing registry, provider routing, market-session, and gap behavior

### Requirement: Historical price response is minimal and provider-agnostic
A successful historical price response SHALL contain exactly `symbol`, `price`, and `pricedAt`.
`price` SHALL be the selected one-minute candle close serialized as a decimal string, and
`pricedAt` SHALL be the selected one-minute candle open serialized as an ISO-8601 UTC timestamp.

#### Scenario: Successful response fields are serialized
- **WHEN** the gateway finds a one-minute candle for the requested instant
- **THEN** the response contains exactly `symbol`, `price`, and `pricedAt`
- **AND** it does not contain timeframe, OHLC fields, volume, asset class, provider identity,
  provider symbol, freshness, or source metadata

#### Scenario: Decimal price is serialized as a string
- **WHEN** the selected candle close is returned
- **THEN** `price` is serialized as a fixed-point decimal string without binary floating-point
  conversion or scientific notation

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

#### Scenario: No candle is available for the requested instant
- **WHEN** the existing one-minute candle flow returns no eligible candle for the resolved bucket
- **THEN** the gateway responds with HTTP status `404`
- **AND** the error code is `PRICE_NOT_FOUND`

#### Scenario: Persistence is unavailable
- **WHEN** registry or candle persistence cannot be queried or updated
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `DATABASE_UNAVAILABLE`

#### Scenario: Selected provider fails
- **WHEN** the selected candle provider fails while filling the one-minute bucket
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `PROVIDER_UNAVAILABLE`
