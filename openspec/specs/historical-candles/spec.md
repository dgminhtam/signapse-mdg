# Historical Candles Specification

## Purpose

Define the provider-agnostic historical candle HTTP contract, validation, provider fill, and
PostgreSQL persistence behavior.
## Requirements
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
- **THEN** its OHLCV values are fixed-point decimal strings without binary floating-point
  conversion or scientific notation
- **AND** its open and close times are ISO-8601 UTC timestamps

#### Scenario: Candles have deterministic order
- **WHEN** more than one candle is returned
- **THEN** the candles are ordered by `openTime` ascending

### Requirement: Initial candle timeframes are explicitly supported

The gateway SHALL support public timeframes `1m`, `5m`, `15m`, `1h`, and `1d` and SHALL map them to
the corresponding interval inside the selected provider adapter boundary.

#### Scenario: Supported timeframe is requested

- **WHEN** a client requests `1m`, `5m`, `15m`, `1h`, or `1d`
- **THEN** the gateway resolves the corresponding interval for the symbol's persisted provider

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

### Requirement: Database work does not span provider waits

The candle flow MUST close its database read session before awaiting the selected provider and
SHALL perform upserts in a separate short transaction.

#### Scenario: Cache miss requires provider data

- **WHEN** a repository read identifies a missing candle range
- **THEN** the read session and transaction are closed before the provider call begins
- **AND** a separate transaction is used to persist complete fetched candles

### Requirement: Candle failures use stable gateway errors

The endpoint SHALL return the standard gateway error envelope and SHALL NOT expose database
credentials, SQL, SDK exceptions, raw provider payloads, credentials, or stack traces.

#### Scenario: Request query shape is invalid

- **WHEN** a required candle query parameter is missing or malformed
- **THEN** the gateway responds with a documented `400` gateway error
- **AND** it does not return FastAPI's default `422` validation response

#### Scenario: Candle persistence is unavailable

- **WHEN** registry or candle persistence cannot be queried or updated
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `DATABASE_UNAVAILABLE`

#### Scenario: Selected candle provider fails

- **WHEN** the selected provider SDK fails, provider configuration is unavailable, or its response
  cannot be safely normalized
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `PROVIDER_UNAVAILABLE`

### Requirement: Real-time candle events maintain current in-memory state
The gateway SHALL maintain at most one current forming candle per canonical `(symbol, timeframe)`
from valid normalized WebSocket candle events and SHALL make that state available to the
historical candle service.

#### Scenario: Forming candle update is received
- **WHEN** a valid stream candle has `complete=false`
- **THEN** it replaces the current in-memory candle for the same symbol and timeframe

#### Scenario: HTTP range includes a cached forming candle
- **WHEN** `GET /v1/candles` covers the open time of the matching current in-memory candle
- **THEN** the service merges that candle into the response by open time
- **AND** returns it with `complete=false`
- **AND** does not persist it

#### Scenario: Cached forming candle falls outside the HTTP range
- **WHEN** the current in-memory candle open time is outside `[from,to)`
- **THEN** it is not included in the response

### Requirement: Completed stream candles are persisted without blocking fanout
The gateway SHALL remove a completed candle from current in-memory state, emit it to matching
clients, and enqueue an idempotent PostgreSQL upsert using the existing candle identity and
repository boundary. Persistence MUST NOT run inside the provider SDK callback or block live
fanout.

#### Scenario: Stream candle closes
- **WHEN** a valid normalized stream candle has `complete=true`
- **THEN** it is removed from current forming state if it matches that series and open time
- **AND** it is enqueued for idempotent persistence
- **AND** matching downstream clients receive the completed candle without waiting for PostgreSQL

#### Scenario: Completed candle already exists
- **WHEN** PostgreSQL already contains the same provider, provider symbol, timeframe, and open time
- **THEN** the repository upsert updates it idempotently
- **AND** no duplicate candle row is created

#### Scenario: Stream candle persistence fails
- **WHEN** PostgreSQL cannot persist a completed streamed candle
- **THEN** live event fanout continues
- **AND** the failure is logged without credentials, SQL, or raw provider payload
- **AND** later historical requests remain able to fill the missing candle through the existing
  provider REST path

### Requirement: Forex historical candles are available through the existing endpoint

The gateway SHALL allow enabled `EUR/USD`, `GBP/USD`, `USD/JPY`, `AUD/USD`, `XAU/USD`, `AAPL`,
`TSLA`, `NVDA`, and `MSFT` registry mappings using provider `TWELVE_DATA` to be requested through
the existing `GET /v1/candles` contract.

#### Scenario: Forex candle range requires provider data

- **WHEN** a valid Forex candle request contains one or more slots not available as persisted
  complete candles
- **THEN** the gateway requests the missing ranges from the Twelve Data Forex adapter
- **AND** the successful response preserves the existing provider-agnostic candle shape

#### Scenario: Forex candle range is fully persisted

- **WHEN** every requested Forex candle slot is available as a persisted complete candle
- **THEN** the gateway returns those persisted candles
- **AND** it makes no Twelve Data request
- **AND** the response can succeed without a configured Twelve Data API key

#### Scenario: Twelve Data is not configured

- **WHEN** a Forex candle request requires a live provider fill
- **AND** Twelve Data configuration is missing or unusable
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `PROVIDER_UNAVAILABLE`
- **AND** Binance-backed crypto candle requests remain available

### Requirement: Candle provider fills are routed by persisted provider mapping

The gateway SHALL route every candle provider fill using the enabled symbol's persisted `provider`
and `provider_symbol` values.

#### Scenario: Crypto candle range requires provider data

- **WHEN** an enabled `BINANCE_SPOT` candle request requires a provider fill
- **THEN** the gateway delegates the missing range to the Binance candle adapter

#### Scenario: Forex candle range requires provider data

- **WHEN** an enabled `TWELVE_DATA` candle request requires a provider fill
- **THEN** the gateway delegates the missing range to the Twelve Data Forex adapter

#### Scenario: Persisted provider is unsupported or unavailable

- **WHEN** a candle request requires a provider fill
- **AND** no usable candle adapter is registered for the persisted provider
- **THEN** the gateway raises the sanitized provider-unavailable boundary
- **AND** it does not fall back to a different provider

### Requirement: Twelve Data Forex candles preserve gateway range semantics

The Twelve Data adapter SHALL map supported public timeframes to Twelve Data intervals, SHALL
request UTC ascending time-series data bounded to the gateway's half-open range, and SHALL return
only candles whose open times satisfy `from <= open_time < to`.

#### Scenario: Half-open Forex range is requested

- **WHEN** the gateway requests a Twelve Data range `[from,to)`
- **THEN** the adapter sends `start_date` equal to `from`
- **AND** it sends `end_date` equal to the final eligible candle open time before `to`
- **AND** it sends `outputsize` equal to the expected gateway slot count
- **AND** it requests UTC timestamps in ascending order

#### Scenario: Provider includes an ineligible boundary row

- **WHEN** Twelve Data returns a row whose open time equals or exceeds `to`
- **THEN** that row is not included in the normalized result
- **AND** no out-of-range candle is persisted or exposed

### Requirement: Forex volume absence is normalized explicitly

The Twelve Data Forex adapter SHALL represent an omitted or null provider volume as exact decimal
zero because the existing public and persistence candle contracts require a non-null volume.

#### Scenario: Forex row omits volume

- **WHEN** a valid Twelve Data Forex OHLC row has no `volume` field or has a null `volume`
- **THEN** the normalized candle volume is `Decimal("0")`
- **AND** the API serializes it as a fixed-point decimal string

#### Scenario: Forex row supplies malformed volume

- **WHEN** a Twelve Data row supplies a non-null volume that is non-decimal, negative, or non-finite
- **THEN** the adapter raises the sanitized provider-unavailable boundary

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
