## ADDED Requirements

### Requirement: Historical candles can be requested by canonical series
The gateway SHALL expose `GET /v1/candles` for one canonical symbol, one supported timeframe, and
one UTC time range.

#### Scenario: Valid candle request
- **WHEN** a client requests an enabled canonical symbol, supported timeframe, and valid range
- **THEN** the gateway responds with HTTP status `200`
- **AND** the response represents that canonical symbol and timeframe

### Requirement: The candle response is minimal and provider-agnostic
The successful response SHALL contain exactly `symbol`, `timeframe`, `from`, `to`, and `candles` at
the top level and MUST NOT expose asset class, provider identity, or provider symbol.

Each candle SHALL contain exactly `openTime`, `closeTime`, `open`, `high`, `low`, `close`, `volume`,
and `complete`.

#### Scenario: Successful response fields are serialized
- **WHEN** the gateway returns candles successfully
- **THEN** the top-level response contains only `symbol`, `timeframe`, `from`, `to`, and `candles`
- **AND** it does not contain `assetClass`, `provider`, or `providerSymbol`
- **AND** each candle contains only the documented candle fields

#### Scenario: Decimal and timestamp values are serialized
- **WHEN** a normalized candle is returned
- **THEN** its OHLCV values are decimal strings without conversion through binary floating point
- **AND** its open and close times are ISO-8601 UTC timestamps

#### Scenario: Candles have deterministic order
- **WHEN** more than one candle is returned
- **THEN** the candles are ordered by `openTime` ascending

### Requirement: Initial candle timeframes are explicitly supported
The gateway SHALL support public timeframes `1m`, `5m`, `15m`, `1h`, and `1d` and SHALL map them to
the corresponding Binance intervals inside the provider adapter boundary.

#### Scenario: Supported timeframe is requested
- **WHEN** a client requests `1m`, `5m`, `15m`, `1h`, or `1d`
- **THEN** the gateway resolves the corresponding provider interval

#### Scenario: Unsupported timeframe is requested
- **WHEN** a client requests any other timeframe
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `UNSUPPORTED_TIMEFRAME`
- **AND** the sanitized error details identify the rejected timeframe

### Requirement: Candle ranges use aligned half-open UTC semantics
The gateway SHALL interpret the requested range as `[from, to)`, with `from` inclusive and `to`
exclusive. Both values MUST be timezone-aware UTC timestamps, `from` MUST be earlier than `to`, and
both values MUST align to boundaries of the requested timeframe.

#### Scenario: Boundary candles are selected
- **WHEN** a valid request covers `[from, to)`
- **THEN** a candle whose open time equals `from` is eligible for the response
- **AND** a candle whose open time equals `to` is excluded

#### Scenario: Time range parameter is missing or malformed
- **WHEN** `from` or `to` is missing, is not a valid timestamp, or is not explicitly UTC
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Time range is inverted or empty
- **WHEN** `from` is equal to or later than `to`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Time range is not timeframe-aligned
- **WHEN** either boundary is not aligned to the requested timeframe
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

### Requirement: Candle requests are bounded
The gateway SHALL reject a request that exceeds either `MAX_CANDLE_RANGE_DAYS` or
`MAX_CANDLES_PER_REQUEST`, with defaults of 30 days and 1,000 expected candles respectively.

#### Scenario: Elapsed range is too wide
- **WHEN** the difference between `from` and `to` exceeds `MAX_CANDLE_RANGE_DAYS`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Expected candle count is too large
- **WHEN** the aligned range contains more than `MAX_CANDLES_PER_REQUEST` timeframe slots
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

### Requirement: Candle symbols come from the enabled registry
The gateway MUST resolve the canonical symbol through the PostgreSQL-backed enabled symbol
registry before accessing candle persistence or the provider.

#### Scenario: Enabled canonical symbol is requested
- **WHEN** the requested symbol is enabled in the registry
- **THEN** the gateway uses its internal asset class, provider, and provider-symbol mapping for
  persistence and provider routing
- **AND** those internal values are not exposed in the candle response

#### Scenario: Unknown or disabled symbol is requested
- **WHEN** the requested canonical symbol is absent from the enabled registry
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `UNSUPPORTED_SYMBOL`
- **AND** no candle provider call is made

### Requirement: Closed candles are reused from PostgreSQL
The gateway SHALL query persisted complete candles before calling the provider and SHALL identify
missing timeframe slots within the requested range.

#### Scenario: Complete range is persisted
- **WHEN** every requested candle slot is available as a persisted complete candle
- **THEN** the gateway returns the persisted candles
- **AND** it makes no Binance kline request

#### Scenario: Part of the range is missing
- **WHEN** one or more contiguous sections of the requested range are absent from persistence
- **THEN** the gateway requests only those missing sections from the provider
- **AND** it merges valid fetched candles with persisted candles by open time

#### Scenario: Provider omits an expected slot
- **WHEN** the provider returns no candle for an expected missing slot
- **THEN** the gateway returns the valid available candles after the fill attempt
- **AND** it does not synthesize an OHLCV candle

### Requirement: Binance klines are fetched through the official SDK
The Binance adapter SHALL use the official SDK `klines` operation with explicit provider symbol,
interval, start time, end time, and limit. Synchronous SDK work MUST execute outside the ASGI event
loop and shared SDK client access SHALL remain serialized.

#### Scenario: Missing range requires provider data
- **WHEN** the service requests a missing Binance candle range
- **THEN** the adapter calls the official SDK `klines` operation
- **AND** the SDK receives the inclusive start time and an end time equivalent to the exclusive
  gateway boundary minus one millisecond
- **AND** no direct HTTP transport is used

#### Scenario: SDK operation is slow
- **WHEN** the synchronous SDK kline operation waits for network I/O
- **THEN** unrelated async gateway work can continue on the event loop

#### Scenario: Async caller is cancelled
- **WHEN** the task awaiting a Binance kline operation is cancelled
- **THEN** cancellation propagates
- **AND** it is not converted into a provider error

### Requirement: Provider candles are strictly normalized
The Binance adapter SHALL convert valid kline arrays to repository-owned candle models using
`Decimal` and UTC datetime values and MUST reject malformed, duplicate, invalid, or inconsistent
provider data.

#### Scenario: Valid Binance klines are returned
- **WHEN** Binance returns valid unique kline arrays inside the requested range
- **THEN** the adapter normalizes their open time, close time, OHLC values, and volume
- **AND** it ignores provider fields that are outside the gateway candle model

#### Scenario: Binance payload is invalid
- **WHEN** a kline is malformed, has a non-finite or invalid OHLCV value, has inconsistent
  timestamps, duplicates an open time, or falls outside the requested range
- **THEN** the adapter raises the sanitized provider-unavailable boundary
- **AND** no SDK model or raw provider payload is exposed

### Requirement: Only complete candles are persisted
The gateway SHALL determine completion from the candle close time and gateway receive time, SHALL
upsert complete candles using `(provider, provider_symbol, timeframe, open_time)`, and MUST NOT
persist a forming candle.

#### Scenario: Provider returns closed candles
- **WHEN** fetched candles have close times earlier than the gateway receive time
- **THEN** they are returned with `complete=true`
- **AND** they are upserted idempotently into PostgreSQL

#### Scenario: Provider returns the current forming candle
- **WHEN** a fetched candle has not closed at the gateway receive time
- **THEN** it may be returned with `complete=false`
- **AND** it is not persisted

#### Scenario: Persisted and provider candles overlap
- **WHEN** a fetched candle has the same identity as a persisted complete candle
- **THEN** the persisted complete candle is retained in the response merge
- **AND** the response contains only one candle for that open time

### Requirement: Database work does not span provider waits
The candle flow MUST close its database read session before awaiting Binance and SHALL perform
upserts in a separate short transaction.

#### Scenario: Cache miss requires Binance
- **WHEN** a repository read identifies a missing candle range
- **THEN** the read session and transaction are closed before the provider call begins
- **AND** a separate transaction is used to persist complete fetched candles

### Requirement: Candle failures use stable gateway errors
The endpoint SHALL return the standard gateway error envelope and SHALL NOT expose database
credentials, SQL, SDK exceptions, raw provider payloads, or stack traces.

#### Scenario: Request query shape is invalid
- **WHEN** a required candle query parameter is missing or malformed
- **THEN** the gateway responds with a documented `400` gateway error
- **AND** it does not return FastAPI's default `422` validation response

#### Scenario: Candle persistence is unavailable
- **WHEN** registry or candle persistence cannot be queried or updated
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `DATABASE_UNAVAILABLE`

#### Scenario: Binance candle request fails
- **WHEN** the official SDK fails or its response cannot be safely normalized
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `PROVIDER_UNAVAILABLE`
