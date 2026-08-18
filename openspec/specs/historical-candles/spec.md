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
### Requirement: Candle ranges use aligned half-open UTC semantics
The gateway SHALL interpret the requested range as exact half-open instants `[from, to)`.
`from` MUST be explicitly UTC. An explicit `to` MUST be explicitly UTC; when omitted, the gateway
SHALL resolve it to one captured request-time UTC instant. `from` MUST be earlier than resolved
`to`. Public boundaries are not required to align to timeframe boundaries.

#### Scenario: Boundary candles are selected
- **WHEN** a valid request covers `[from, to)`
- **THEN** a candle whose open time equals `from` is eligible for the response
- **AND** a candle whose open time equals `to` is excluded
- **AND** candles strictly between the exact boundaries are eligible

#### Scenario: To parameter is omitted
- **WHEN** a valid request omits `to`
- **THEN** the gateway captures current UTC once and uses it for validation, provider access, and
  response serialization

#### Scenario: Time range parameter is missing or malformed
- **WHEN** `from` is missing, an explicit `to` is empty, or either supplied value is not explicitly
  UTC
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Time range is inverted or empty
- **WHEN** `from` is equal to or later than `to`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Time range is not timeframe-aligned
- **WHEN** either boundary is not aligned to the requested timeframe
- **THEN** the gateway accepts the range and filters actual provider open times within it

### Requirement: Candle requests are bounded
The gateway SHALL reject an exact-range or slot-based request that exceeds
`MAX_CANDLES_PER_REQUEST`, with a default of 1,000 expected candles or eligible slots. A
provider-backed `count` request SHALL accept values from 1 through 1,000. Count-mode scanning SHALL
also be bounded by a separate internal maximum number of eligible slots inspected.

#### Scenario: Expected candle count is too large
- **WHEN** either the conservative or exact scheduled count exceeds `MAX_CANDLES_PER_REQUEST`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Slot-based request exceeds the maximum
- **WHEN** a `limit` request would derive more than `MAX_CANDLES_PER_REQUEST` eligible slots
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Provider-backed count exceeds the maximum
- **WHEN** a `count` request supplies a value greater than 1,000
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Monthly range is counted by calendar opens
- **WHEN** a `1mo` request spans calendar-month candle opens
- **THEN** the exact scheduled count is based on eligible monthly open timestamps inside
  `[from,to)`
- **AND** no fixed 30-day duration is used to accept, reject, or fetch monthly candles

#### Scenario: Count scan reaches its internal budget
- **WHEN** a valid provider-backed `count` request has not found the requested number of actual
  candles before the configured eligible-slot scan budget is reached
- **THEN** the gateway stops scanning and responds with HTTP status `200`
- **AND** the response contains the valid provider-backed candles found so far
- **AND** the gateway does not synthesize candles or expose a pagination metadata field
### Requirement: Candle symbols come from the enabled registry

The gateway MUST resolve the canonical symbol through the PostgreSQL-backed enabled symbol registry and resolve one immutable Provider Selection before accessing candle persistence or a provider. Omission of `provider` MUST select the Default Provider, and an explicit value MUST select the exact configured mapping regardless of default state.

#### Scenario: Enabled canonical symbol is requested without an override

- **WHEN** the requested symbol is enabled and `provider` is omitted
- **THEN** the gateway uses its Default Provider and provider symbol for persistence and provider routing
- **AND** those internal values are not exposed in the candle response

#### Scenario: Enabled canonical symbol supports the override

- **WHEN** the requested symbol is enabled and has a mapping matching the Provider Override
- **THEN** the gateway uses that Provider Selection for all persistence and provider operations
- **AND** the response remains provider-agnostic

#### Scenario: Enabled canonical symbol does not support the override

- **WHEN** the requested symbol is enabled but lacks a mapping matching the Provider Override
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `UNSUPPORTED_PROVIDER`
- **AND** sanitized error details identify the canonical symbol and requested provider
- **AND** no candle cache, persistence, or provider call is made

#### Scenario: Unknown or disabled symbol is requested

- **WHEN** the requested canonical symbol is absent from the enabled registry
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `UNSUPPORTED_SYMBOL`
- **AND** no Provider Mapping validation or candle provider call is made

### Requirement: Closed candles are reused from PostgreSQL

The gateway SHALL query persisted complete candles before calling the selected provider, SHALL
discard candles that violate the symbol's market-session policy, and SHALL identify missing
expected opens using the symbol's provider/market candle schedule.

#### Scenario: Complete eligible range is persisted

- **WHEN** every expected eligible candle open is available as a persisted complete candle
- **THEN** the gateway returns the persisted candles
- **AND** it makes no provider candle request

#### Scenario: Part of the eligible range is missing

- **WHEN** one or more expected eligible opens are absent from persistence
- **THEN** the gateway requests only provider windows covering those missing sections from
  the symbol's persisted mapping
- **AND** it merges valid fetched candles with eligible persisted candles by open time

#### Scenario: Provider schedule is offset from UTC epoch
- **WHEN** a provider labels hourly candles at minute thirty
- **THEN** gap detection uses that schedule and recognizes persisted minute-thirty rows

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
using `(provider, provider_symbol, timeframe, open_time)`, and MUST NOT persist a forming
or session-ineligible candle. A normalized eligible forming candle obtained through the REST
candle flow SHALL be stored in the process-local forming snapshot cache with its gateway store
time and SHALL remain available only while its cache TTL and candle close time are valid.

#### Scenario: Provider returns eligible closed candles
- **WHEN** fetched candles are market-session eligible and have close times earlier than the
  gateway receive time
- **THEN** they are returned with `complete=true`
- **AND** they are upserted idempotently into PostgreSQL
- **AND** they are not stored as forming snapshots

#### Scenario: Provider returns the current eligible forming candle
- **WHEN** a fetched market-session eligible candle has not closed at gateway receive time
- **THEN** it may be returned with `complete=false`
- **AND** it is stored in the forming snapshot cache with the resolved Provider Selection and
  timeframe
- **AND** it is not persisted

#### Scenario: Forming snapshot reaches its close time

- **WHEN** the current time reaches or passes a forming snapshot's `closeTime`
- **THEN** the gateway evicts that snapshot
- **AND** it does not relabel the cached object as `complete=true`
- **AND** a subsequent request uses the normal persisted/provider path for the completed candle

#### Scenario: Provider returns a session-ineligible candle
- **WHEN** a fetched candle violates the symbol's market-session policy
- **THEN** it is neither returned nor persisted
- **AND** it is not stored in the forming snapshot cache

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

The endpoint SHALL return the standard gateway error envelope and SHALL NOT expose database credentials, SQL, SDK exceptions, raw provider payloads, credentials, or stack traces.

#### Scenario: Request query shape is invalid

- **WHEN** a required candle query parameter is missing or malformed, or `provider` is empty or repeated
- **THEN** the gateway responds with a documented `400` gateway error
- **AND** an invalid provider query uses code `INVALID_PROVIDER`
- **AND** it does not return FastAPI's default `422` validation response

#### Scenario: Requested provider is unsupported for the asset

- **WHEN** the enabled asset has no mapping matching the requested Provider Identifier
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `UNSUPPORTED_PROVIDER`

#### Scenario: Candle persistence is unavailable

- **WHEN** registry or candle persistence cannot be queried or updated
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `DATABASE_UNAVAILABLE`

#### Scenario: Selected candle provider fails

- **WHEN** the selected provider SDK fails, provider configuration is unavailable, or its response cannot be safely normalized
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `PROVIDER_UNAVAILABLE`
- **AND** the gateway does not fall back to another Provider Mapping

### Requirement: Forex historical candles are available through the existing endpoint

The gateway SHALL allow enabled `BTC/USD`, `ETH/USD`, `EUR/USD`, `GBP/USD`, `USD/JPY`,
`AUD/USD`, `XAU/USD`, `AAPL`, `TSLA`, `NVDA`, and `MSFT` registry mappings using provider
`TWELVE_DATA` to be requested through the existing `GET /v1/candles` contract.

#### Scenario: Twelve Data candle range requires provider data

- **WHEN** a valid Twelve Data-backed candle request contains one or more slots not available as
  persisted complete candles
- **THEN** the gateway requests the missing ranges from the Twelve Data adapter
- **AND** the successful response preserves the existing provider-agnostic candle shape

#### Scenario: Twelve Data candle range is fully persisted

- **WHEN** every requested Twelve Data-backed candle slot is available as a persisted complete
  candle
- **THEN** the gateway returns those persisted candles
- **AND** it makes no Twelve Data request
- **AND** the response can succeed without a configured Twelve Data API key

#### Scenario: Twelve Data is not configured

- **WHEN** a Twelve Data-backed candle request requires a live provider fill
- **AND** Twelve Data configuration is missing or unusable
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `PROVIDER_UNAVAILABLE`
- **AND** other provider-backed candle requests remain available
### Requirement: Candle provider fills are routed by persisted provider mapping

The gateway SHALL use the immutable Provider Selection's `provider` and `provider_symbol` for persisted-candle reads and provider fills. Persisted rows MUST remain owned by their recorded provider identity, and the gateway MUST NOT read, relabel, merge, or fall back to rows owned by another mapping.

#### Scenario: Default-backed candle range requires provider data

- **WHEN** a candle request without a Provider Override requires a provider fill
- **THEN** the gateway delegates the missing range to the Default Provider's candle adapter using its provider symbol

#### Scenario: Override-backed candle range requires provider data

- **WHEN** a candle request with a supported Provider Override requires a provider fill
- **THEN** the gateway delegates the missing range to the selected provider's candle adapter using its provider symbol

#### Scenario: Same canonical series exists for two mappings

- **WHEN** persisted candle rows exist for two Provider Mappings of one canonical symbol and timeframe
- **THEN** the request reads and merges only rows belonging to its selected mapping
- **AND** rows owned by the other mapping are not relabeled or returned

#### Scenario: Default Provider is switched

- **WHEN** a canonical symbol is switched to another Default Provider
- **THEN** subsequent default candle reads and fills use the new provider identity
- **AND** existing candle rows retain their recorded provider and provider symbol

#### Scenario: Selected provider is unsupported operationally

- **WHEN** a candle request requires a provider fill
- **AND** no usable candle adapter is registered for the selected Provider Mapping
- **THEN** the gateway raises the sanitized `PROVIDER_UNAVAILABLE` boundary
- **AND** it does not fall back to a different provider

### Requirement: Forming candle cache is isolated by Provider Selection

The gateway MUST identify each process-local forming candle snapshot by canonical symbol, Provider
Identifier, provider symbol, and timeframe, and MUST record the gateway store time needed for TTL
evaluation. A request MAY reuse a forming snapshot only when it resolves to the same Provider
Mapping and the snapshot has not reached its close time or exceeded the configured forming-cache
TTL.

#### Scenario: Two mappings form the same canonical timeframe

- **WHEN** two Provider Mappings emit forming candles for the same canonical symbol and timeframe
- **THEN** the cache retains independent entries for the two mappings
- **AND** neither entry can satisfy a request selecting the other mapping

#### Scenario: Two timeframes form the same canonical symbol

- **WHEN** forming snapshots exist for two timeframes of the same canonical symbol and Provider
  Selection
- **THEN** the cache retains independent entries for each timeframe
- **AND** a request for one timeframe never returns the other timeframe's snapshot

#### Scenario: Forming snapshot is within TTL and before close time

- **WHEN** a request resolves the same cache key and the snapshot age is at most
  `CANDLE_FORMING_CACHE_TTL_SECONDS`
- **AND** the current time is before its `closeTime`
- **THEN** the gateway may reuse the snapshot
- **AND** it does not treat the snapshot as a completed candle

#### Scenario: Forming snapshot expires by TTL

- **WHEN** a matching forming snapshot is older than
  `CANDLE_FORMING_CACHE_TTL_SECONDS` but its candle interval has not closed
- **THEN** the gateway evicts or replaces the expired entry
- **AND** it attempts a fresh selected-provider load

### Requirement: Forming candle snapshot refreshes are self-contained and single-flight

The gateway SHALL let the REST candle service populate and refresh forming snapshots without any
WebSocket registration. The cache SHALL use a default TTL of five seconds, SHALL expose a typed
deployment setting for that TTL, and SHALL coordinate concurrent misses for the same exact cache
key so that at most one provider request is in flight for that key. A cache hit SHALL be served
without a `429` response.

#### Scenario: First REST request populates a forming snapshot

- **WHEN** a valid candle request requires the current eligible candle and no matching forming
  snapshot exists
- **THEN** the candle service requests the selected provider through the existing candle-provider
  boundary
- **AND** stores an eligible incomplete result in the process-local forming snapshot cache
- **AND** returns it with `complete=false` without requiring an active WebSocket

#### Scenario: Concurrent same-key misses are single-flight

- **WHEN** concurrent requests miss or observe an expired forming snapshot for the same canonical
  symbol, Provider Selection, provider symbol, and timeframe
- **THEN** the gateway makes at most one provider request for that key
- **AND** all waiting requests re-check and use the resulting snapshot or receive the same sanitized
  provider failure

#### Scenario: Different cache keys do not block each other

- **WHEN** concurrent requests miss forming snapshots for different symbols, Provider Selections,
  or timeframes
- **THEN** each key can load independently
- **AND** a slow provider request for one key does not serialize unrelated keys

#### Scenario: Polling within TTL does not return a rate-limit error

- **WHEN** a client polls the same candle key again before the five-second default TTL expires
- **THEN** the gateway returns the cached forming snapshot when it remains before `closeTime`
- **AND** it does not return HTTP `429`

#### Scenario: Expired forming snapshot is not served after provider failure

- **WHEN** a matching forming snapshot has expired by TTL or close time
- **AND** the selected provider cannot refresh it
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `PROVIDER_UNAVAILABLE`
- **AND** it does not return the expired forming snapshot

#### Scenario: Completed candles continue through normal persistence

- **WHEN** a provider fill returns a candle whose close time has passed at gateway receive time
- **THEN** the gateway marks it `complete=true`
- **AND** upserts it through the existing PostgreSQL repository
- **AND** subsequent requests can reuse the completed persisted candle without the forming TTL
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

### Requirement: Historical candles use inline calendar config for eligibility

The historical candle flow SHALL use each enabled symbol's inline calendar config to decide market
session eligibility when that config is present.

#### Scenario: Supported symbol calendar config is loaded

- **WHEN** an enabled symbol is resolved for a historical candle request
- **THEN** its internal symbol value includes `calendar_source`, `calendar_name`, and
  `calendar_timezone`

#### Scenario: Exchange intraday range includes closed slots

- **WHEN** a non-Forex symbol has `calendar_source` set to `pandas_market_calendars`
- **AND** a valid intraday candle request includes slots outside that calendar's open session
- **THEN** closed-session slots do not count as expected candles
- **AND** no provider request is made for closed-session-only sections

#### Scenario: Exchange break window is present

- **WHEN** a pandas calendar schedule contains `break_start` and `break_end`
- **AND** an intraday candle open falls inside the break window
- **THEN** that candle open is ineligible for provider fill, persistence, cache merge, and response
  inclusion

#### Scenario: Exchange daily label is closed

- **WHEN** a non-Forex pandas-calendar symbol has a `1d` candle labeled on a non-session UTC date
- **THEN** that candle is ineligible for provider fill, persistence, cache merge, and response
  inclusion

#### Scenario: Crypto symbol uses internal always-open config

- **WHEN** a symbol has `calendar_source=internal` and `calendar_name=24/7`
- **THEN** its candle eligibility remains always open

#### Scenario: Forex and XAU use the existing weekly quote session

- **WHEN** a Forex pair or spot `XAU/USD` is evaluated for candle eligibility
- **THEN** the existing Sunday 17:00 through Friday 17:00 New York weekly-session behavior is
  preserved

#### Scenario: Calendar config is absent or unsupported

- **WHEN** a supported symbol has no usable inline calendar config
- **THEN** the gateway falls back to the existing asset-class market-session policy

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

### Requirement: WTI and ETF historical candles use the existing endpoint

The gateway SHALL serve enabled `WTI`, `SPY`, and `QQQ` through `GET /v1/candles`.

#### Scenario: Missing WTI or ETF range is requested
- **WHEN** eligible slots are absent from persistence and current cache
- **THEN** only missing eligible ranges are requested from Twelve Data

### Requirement: ETF candles use the regular US market session

ETF intraday slots SHALL be eligible Monday-Friday 09:30-16:00 in `America/New_York`; daily slots
SHALL use UTC weekdays.

#### Scenario: ETF range spans session boundaries
- **WHEN** a range includes closed and regular-session slots
- **THEN** only regular-session slots count as expected candles

### Requirement: WTI candles use the configured energy session

WTI intraday slots SHALL use Sunday 18:00-Friday 17:00 in `America/New_York`, excluding the
Monday-Thursday 17:00-18:00 maintenance window.

#### Scenario: WTI range spans a closure
- **WHEN** a range includes weekly closure or daily maintenance
- **THEN** closed slots do not count as missing candles

### Requirement: Natural WTI and ETF provider gaps are preserved

The gateway MUST NOT synthesize missing WTI, SPY, or QQQ candles.

#### Scenario: Provider returns a partial eligible range
- **WHEN** Twelve Data omits eligible rows
- **THEN** valid rows are retained without fabricating omitted candles

### Requirement: Provider candle timestamps remain authoritative

The gateway MUST preserve valid provider candle open timestamps and MUST NOT shift them to fit a
universal epoch-aligned grid.

#### Scenario: Twelve Data returns an hourly candle at minute thirty
- **WHEN** a valid Twelve Data hourly candle opens at `13:30Z`
- **THEN** its normalized `openTime` remains `13:30Z`
- **AND** its close time is derived from that actual open time

### Requirement: Twelve Data no-data ranges are successful empty results

The Twelve Data adapter SHALL distinguish its recognized no-data time-series condition from
operational and contract failures.

#### Scenario: Provider reports no data for specified dates
- **WHEN** Twelve Data returns the recognized no-data condition for a valid range
- **THEN** the adapter returns zero candles
- **AND** the endpoint can respond with HTTP `200` and an empty `candles` array

#### Scenario: Provider returns another error
- **WHEN** Twelve Data reports authentication, entitlement, rate-limit, invalid-parameter,
  unknown-symbol, timeout, transport, or unrecognized failure
- **THEN** the adapter raises the sanitized provider-unavailable boundary

### Requirement: YFINANCE historical candles use the existing endpoint

The gateway SHALL allow any enabled canonical asset whose active persisted mapping uses one of the
23 approved `YFINANCE` provider symbols to be requested through the existing `GET /v1/candles`
contract.

#### Scenario: YFINANCE candle range requires provider data

- **WHEN** a valid yfinance-backed candle request contains one or more slots not available as
  persisted complete candles
- **THEN** the gateway requests the missing ranges from the yfinance candle adapter
- **AND** the successful response preserves the existing provider-agnostic candle shape

#### Scenario: Inactive yfinance alternative is selected manually

- **WHEN** an approved inactive yfinance alternative becomes the asset's active persisted mapping
- **AND** its candle request requires a provider fill
- **THEN** the gateway requests the persisted yfinance provider symbol
- **AND** it does not read or fetch candles under the previous provider identity

#### Scenario: YFINANCE candle range is fully persisted

- **WHEN** every requested yfinance-backed candle slot is available as a persisted complete candle
- **THEN** the gateway returns those persisted candles
- **AND** it makes no yfinance request

#### Scenario: YFINANCE provider fails

- **WHEN** a yfinance-backed candle request requires a live provider fill
- **AND** yfinance or Yahoo Finance cannot provide a usable response
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `PROVIDER_UNAVAILABLE`
- **AND** Binance-backed and Twelve Data-backed candle requests remain available

### Requirement: YFINANCE candle fills are routed by persisted provider mapping

The gateway SHALL route yfinance candle provider fills using the enabled symbol's persisted
`provider` and `provider_symbol` values.

#### Scenario: YFINANCE candle range requires provider data

- **WHEN** an enabled `YFINANCE` candle request requires a provider fill
- **THEN** the gateway delegates the missing range to the yfinance candle adapter
- **AND** it uses the persisted yfinance provider symbol for the upstream request
- **AND** it does not fall back to a different provider

### Requirement: YFINANCE candles preserve gateway range semantics

The yfinance adapter SHALL map supported public timeframes to yfinance intervals, SHALL request
historical data using the gateway's half-open UTC range, and SHALL return only candles whose open
times satisfy `from <= open_time < to`.

#### Scenario: Half-open YFINANCE range is requested

- **WHEN** the gateway requests a yfinance range `[from,to)`
- **THEN** the adapter sends `start` equal to `from`
- **AND** it sends `end` equal to `to`
- **AND** it requests the yfinance interval matching the public timeframe

#### Scenario: Provider includes an ineligible boundary row

- **WHEN** yfinance returns a row whose open time equals or exceeds `to`
- **THEN** that row is not included in the normalized result
- **AND** no out-of-range candle is persisted or exposed

### Requirement: YFINANCE candle timestamps remain authoritative

The gateway MUST preserve valid yfinance candle open timestamps after UTC normalization and MUST
NOT shift them to fit a universal epoch-aligned grid.

#### Scenario: YFINANCE returns an offset candle timestamp

- **WHEN** a valid yfinance candle row opens at a timestamp that is not aligned to the UTC epoch
  grid for the requested timeframe
- **THEN** its normalized `openTime` remains that provider timestamp converted to UTC
- **AND** its `closeTime` is derived from that actual open time and requested timeframe duration

### Requirement: YFINANCE OHLCV rows are normalized strictly

The yfinance adapter SHALL convert valid history rows to repository-owned candle models
using `Decimal` values and UTC datetimes and MUST reject malformed, duplicate, invalid,
or structurally unsafe provider data. An individual row whose only failure is an
inconsistent OHLC envelope MAY be quarantined when at least one other eligible row in
the same non-empty payload is valid; the adapter MUST NOT repair or synthesize that row.

#### Scenario: Valid YFINANCE rows are returned

- **WHEN** yfinance returns valid unique rows inside the requested range
- **THEN** the adapter normalizes open time, close time, OHLC values, and volume
- **AND** it ignores provider fields that are outside the gateway candle model

#### Scenario: YFINANCE row omits volume

- **WHEN** a valid yfinance row has no volume value or has a null volume value
- **THEN** the normalized candle volume is `Decimal("0")`
- **AND** the API serializes it as a fixed-point decimal string

#### Scenario: Isolated YFINANCE OHLC bounds violation is quarantined

- **WHEN** a non-empty yfinance payload contains one row where `High` is below
  `max(Open, Close)` or `Low` is above `min(Open, Close)`
- **AND** at least one other eligible row in the payload has valid timestamp and OHLCV
  values
- **THEN** the adapter excludes the inconsistent row from normalized candles
- **AND** it returns the other valid rows
- **AND** it does not repair, clamp, round, persist, or expose the inconsistent row

#### Scenario: All YFINANCE rows fail only the OHLC bounds check

- **WHEN** a non-empty yfinance payload contains no row that can be normalized because
  every eligible row violates the OHLC bounds check
- **THEN** the adapter raises the sanitized provider-unavailable boundary
- **AND** the failure reason is `INVALID_PAYLOAD`
- **AND** no partial candle result is returned

#### Scenario: YFINANCE payload has a batch-fatal row error

- **WHEN** a yfinance row has an invalid timestamp, duplicate timestamp, missing
  required OHLC field, malformed/non-finite OHLCV value, negative volume, or another
  structural normalization failure
- **THEN** the adapter raises the sanitized provider-unavailable boundary for the
  entire payload
- **AND** it does not continue with a partial result
- **AND** no yfinance DataFrame, exception, or raw provider payload is exposed

### Requirement: Natural YFINANCE provider gaps are preserved

The gateway MUST preserve absent yfinance candle slots as gaps and MUST NOT fabricate
OHLCV candles for omitted provider data or quarantined provider rows.

#### Scenario: Provider returns no candles for a valid range

- **WHEN** a valid yfinance-backed request covers eligible slots for which yfinance returns no rows
- **THEN** the gateway returns the valid available candles, which may be an empty list
- **AND** it does not create or persist synthetic candles

#### Scenario: Provider returns only part of a YFINANCE range

- **WHEN** yfinance omits one or more eligible slots but returns other valid rows
- **THEN** the gateway returns and persists only the valid eligible complete rows
- **AND** the omitted eligible slots remain absent

#### Scenario: Provider quarantines one row in a partially valid range

- **WHEN** yfinance returns valid rows together with an isolated OHLC-bounds-invalid row
- **THEN** the gateway returns and persists/cache-merges the valid eligible rows
- **AND** the quarantined row's timestamp remains absent from the response and storage
- **AND** the public response keeps the existing candle response shape

### Requirement: Historical candles can be requested by eligible count

The gateway SHALL allow `GET /v1/candles` clients to request the latest eligible candle slots using
`limit` instead of `from`. Count requests SHALL be self-contained and MUST NOT require an active
WebSocket quote subscription. For `limit=1`, the gateway SHALL return the latest eligible
available candle: a valid forming snapshot when available, otherwise the latest completed candle;
when neither is available it SHALL return an empty `candles` array.

#### Scenario: Count request resolves latest eligible opens

- **WHEN** a client requests an enabled canonical symbol, supported timeframe, valid `limit`, and
  no `from`
- **THEN** the gateway derives the latest `limit` eligible candle opens at or before the resolved
  `to` boundary using the symbol's candle schedule and market-session policy
- **AND** the gateway uses those derived opens for persistence lookup, provider gap fill, cache
  forming snapshot merge, and response filtering

#### Scenario: Count request omits to

- **WHEN** a valid count request omits `to`
- **THEN** the gateway captures current UTC once and uses it as the exclusive upper boundary for
  count derivation, provider access, and response serialization

#### Scenario: Candle request works without an active WebSocket

- **WHEN** a client requests `GET /v1/candles?symbol=TSLA&timeframe=1m&limit=1` without any active
  quote stream
- **THEN** the gateway resolves the registry, forming snapshot cache, PostgreSQL, and selected
  candle provider as needed
- **AND** it returns the normal provider-agnostic candle response

#### Scenario: Fresh forming snapshot is the latest available candle

- **WHEN** `limit=1` resolves an eligible open time with a fresh forming snapshot
- **THEN** the gateway returns that snapshot with `complete=false`
- **AND** it does not make a provider request solely to refresh the snapshot

#### Scenario: Latest completed candle is returned when no forming snapshot is available

- **WHEN** `limit=1` has no valid forming snapshot but has an eligible completed candle from
  PostgreSQL or a successful provider fill
- **THEN** the gateway returns the latest completed candle with `complete=true`

#### Scenario: No eligible candle is available

- **WHEN** `limit=1` has no valid forming snapshot, no persisted complete candle, and the selected
  provider returns no eligible candle
- **THEN** the gateway responds with HTTP status `200`
- **AND** the response contains `candles: []`

#### Scenario: Count request crosses closed sessions

- **WHEN** a count request crosses weekends, holidays, maintenance breaks, or pandas calendar break
  windows
- **THEN** closed-session candle opens do not count toward `limit`
- **AND** no provider request is made for closed-session-only sections

#### Scenario: Count request encounters natural provider gaps

- **WHEN** a provider omits one or more derived eligible candle slots
- **THEN** the gateway returns the valid available candles, which can be fewer than `limit`
- **AND** it does not synthesize missing candles or issue provider-specific paging retries to force
  exactly `limit` rows

#### Scenario: Count request uses cached forming candle

- **WHEN** a current cached forming candle matches one of the derived eligible opens
- **THEN** the gateway can merge that candle into the response with `complete=false`
- **AND** it does not persist the forming candle

### Requirement: Historical candle range and count modes are unambiguous

The gateway SHALL treat `from`/`to` range requests and `limit` count requests as distinct request
modes.

#### Scenario: Range request behavior is preserved

- **WHEN** a client supplies `from` and omits `limit`
- **THEN** the gateway preserves the existing half-open `[from,to)` range semantics

#### Scenario: Count request supplies from

- **WHEN** a client supplies both `from` and `limit`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Count request has invalid limit

- **WHEN** `limit` is missing in count mode, non-integer, less than one, or greater than
  `MAX_CANDLES_PER_REQUEST`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Count request keeps response shape

- **WHEN** the gateway returns candles for a valid count request
- **THEN** the response contains the existing `symbol`, `timeframe`, `from`, `to`, and `candles`
  fields
- **AND** `from` is the first derived eligible open when any eligible opens exist
- **AND** `to` is the resolved exclusive upper boundary

### Requirement: Historical candles can be requested by forward eligible count

The gateway SHALL allow `GET /v1/candles` clients to request eligible candle slots forward from an
explicit UTC `from` boundary by supplying `from` and `limit` without `to`.

#### Scenario: Forward count request resolves next eligible opens

- **WHEN** a client requests an enabled canonical symbol, supported timeframe, valid UTC `from`,
  valid `limit`, and no `to`
- **THEN** the gateway derives the next `limit` eligible candle opens at or after `from` using the
  symbol's candle schedule and market-session policy
- **AND** the gateway uses those derived opens for persistence lookup, provider gap fill, cache
  merge, and response filtering

#### Scenario: Forward count request skips closed sessions

- **WHEN** a forward count request crosses weekends, holidays, maintenance breaks, or pandas
  calendar break windows
- **THEN** closed-session candle opens do not count toward `limit`
- **AND** no provider request is made for closed-session-only sections

#### Scenario: Forward count request preserves response shape

- **WHEN** the gateway returns candles for a valid forward count request
- **THEN** the response contains the existing `symbol`, `timeframe`, `from`, `to`, and `candles`
  fields
- **AND** `from` is the first derived eligible open when any eligible opens exist
- **AND** `to` is the exclusive boundary immediately after the final derived eligible open when any
  eligible opens exist

### Requirement: Historical candle count mode query combinations are unambiguous

The gateway SHALL assign a single meaning to each supported `from`, `to`, `limit`, and `count`
query combination and MUST reject combinations that mix exact-range, slot-limit, and
provider-backed-row-count semantics.

#### Scenario: Explicit range request uses from and to

- **WHEN** a client supplies `from` and `to` without `limit` or `count`
- **THEN** the gateway preserves the existing half-open `[from,to)` range semantics

#### Scenario: Forward slot-limit request uses from and limit

- **WHEN** a client supplies `from` and `limit` without `to` or `count`
- **THEN** the gateway treats the request as forward eligible-slot mode from `from`

#### Scenario: Backward slot-limit request uses to and limit

- **WHEN** a client supplies `to` and `limit` without `from` or `count`
- **THEN** the gateway treats the request as backward eligible-slot mode before `to`

#### Scenario: Latest slot-limit request omits boundaries

- **WHEN** a client supplies `limit` without `from`, `to`, or `count`
- **THEN** the gateway treats the request as latest eligible-slot mode before one captured
  request-time UTC instant

#### Scenario: Latest provider-backed count request omits boundaries

- **WHEN** a client supplies `count` without `from`, `to`, or `limit`
- **THEN** the gateway treats the request as latest provider-backed-row mode before one captured
  request-time UTC instant

#### Scenario: Forward provider-backed count request uses from and count

- **WHEN** a client supplies `from` and `count` without `to` or `limit`
- **THEN** the gateway treats the request as provider-backed-row mode at or after `from`

#### Scenario: Backward provider-backed count request uses to and count

- **WHEN** a client supplies `to` and `count` without `from` or `limit`
- **THEN** the gateway treats the request as provider-backed-row mode strictly before `to`

#### Scenario: Slot-limit request supplies both range boundaries

- **WHEN** a client supplies `from`, `to`, and `limit`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Provider-backed count request supplies both range boundaries

- **WHEN** a client supplies `from`, `to`, and `count`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Request mixes limit and count

- **WHEN** a client supplies both `limit` and `count`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

### Requirement: Candle values are independent of display precision

The gateway SHALL preserve normalized and persisted candle OHLCV values independently of symbol
`price_display_decimals`, SHALL serialize public candle `open`, `high`, `low`, and `close` with
`ROUND_HALF_UP` rounding and exact fractional-digit padding, and SHALL leave `volume` independent
of price display precision.

#### Scenario: Candle OHLC has more fractional digits than display metadata

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** a normalized candle contains `open`, `high`, `low`, and `close` values with more than two
  fractional digits
- **THEN** each public OHLC field is rounded with `ROUND_HALF_UP` and contains exactly two
  fractional digits
- **AND** the normalized and persisted OHLC values remain unchanged

#### Scenario: Candle response shape remains unchanged

- **WHEN** historical candles are returned successfully
- **THEN** the response and each candle continue to contain only their documented fields
- **AND** neither contains `priceDisplayDecimals`

#### Scenario: Volume is unaffected

- **WHEN** a candle is normalized, persisted, or returned
- **THEN** `price_display_decimals` is not applied to its volume
- **AND** the public volume remains the raw fixed-point decimal string

### Requirement: Historical candles can be requested by provider-backed candle count

The gateway SHALL allow `GET /v1/candles` clients to request up to `count` unique
Provider-backed Candle Snapshots. A result MAY contain fewer snapshots when history is exhausted,
provider or session gaps leave rows absent, or the internal scan budget is reached. The gateway
MUST NOT create synthetic candles to satisfy `count`.

#### Scenario: Latest provider-backed count resolves actual snapshots

- **WHEN** a client requests a valid `count` without `from` or `to`
- **THEN** the gateway searches eligible opens backward from one captured request-time UTC instant
- **AND** it accumulates unique provider-backed snapshots until `count`, history exhaustion, or the
  scan budget is reached

#### Scenario: Forward provider-backed count skips missing eligible slots

- **WHEN** a client requests a valid `from + count` query and the provider omits eligible slots
- **THEN** omitted slots do not consume the returned provider-backed row count
- **AND** the gateway continues scanning eligible opens within the scan budget for later available
  snapshots

#### Scenario: Backward provider-backed count excludes its cutoff

- **WHEN** a client requests a valid `to + count` query
- **THEN** only snapshots with `openTime < to` are eligible
- **AND** a snapshot with `openTime == to` is excluded

#### Scenario: Provider-backed count crosses closed sessions

- **WHEN** a provider-backed count query crosses weekends, holidays, maintenance breaks, or
  configured session breaks
- **THEN** closed-session opens do not consume the scan budget or returned count
- **AND** no provider request is made for closed-session-only sections

#### Scenario: Provider-backed count returns a partial result

- **WHEN** fewer than `count` provider-backed snapshots are available before history exhaustion or
  scan-budget exhaustion
- **THEN** the gateway responds with HTTP status `200`
- **AND** the response contains all valid snapshots found
- **AND** the response does not claim that the result contains exactly `count` rows

#### Scenario: Provider-backed count has no history

- **WHEN** a valid provider-backed count query finds no eligible provider-backed snapshot
- **THEN** the gateway responds with HTTP status `200`
- **AND** the response contains `candles: []`

#### Scenario: Provider-backed count includes a forming snapshot

- **WHEN** an eligible forming snapshot is available for one of the count query's opens
- **THEN** the gateway includes it as one provider-backed snapshot
- **AND** it returns `complete=false`
- **AND** it does not persist the forming snapshot as a completed candle

#### Scenario: Provider-backed count prefers completed data

- **WHEN** persistence, provider fill, or forming cache provides multiple snapshots for the same
  `openTime`
- **THEN** the gateway returns one canonical snapshot for that `openTime`
- **AND** a completed snapshot takes precedence over a forming snapshot
- **AND** the duplicate does not consume more than one count row

#### Scenario: Provider-backed count preserves response shape and order

- **WHEN** a valid provider-backed count query returns one or more snapshots
- **THEN** the response contains only `symbol`, `timeframe`, `from`, `to`, and `candles` at the top
  level
- **AND** the candle list is sorted by `openTime` ascending
- **AND** the response boundaries describe the resolved query boundaries rather than inferred data
  extents

#### Scenario: Provider-backed count is provider-agnostic

- **WHEN** the same count mode is requested for any candle-capable selected Provider Selection
- **THEN** the gateway applies the same row-count, gap, cutoff, ordering, and response semantics
- **AND** it does not silently switch to another Provider Mapping

### Requirement: Unsupported backward query parameters are rejected

The gateway SHALL reject the unsupported `before` query parameter rather than silently ignoring it or
interpreting it as another query mode.

#### Scenario: Client supplies before

- **WHEN** a candle request contains `before`
- **THEN** the gateway responds with HTTP status `400`
- **AND** it returns the documented invalid candle-query error
- **AND** it does not execute a candle provider or persistence query for the invalid request

### Requirement: Provider-backed count validation is explicit

The gateway SHALL validate `count` as an integer in the inclusive range 1 through 1,000 before
executing provider-backed count work.

#### Scenario: Count is not an integer

- **WHEN** a client supplies a non-integer `count`
- **THEN** the gateway responds with HTTP status `400`
- **AND** it does not execute a candle provider or persistence query

#### Scenario: Count is below the minimum

- **WHEN** a client supplies `count < 1`
- **THEN** the gateway responds with HTTP status `400`
- **AND** it does not execute a candle provider or persistence query

#### Scenario: Count is at the maximum

- **WHEN** a client supplies `count=1000`
- **THEN** the gateway accepts the value when the remaining query parameters form a valid count
  mode

#### Scenario: Count exceeds the maximum

- **WHEN** a client supplies `count > 1000`
- **THEN** the gateway responds with HTTP status `400`
- **AND** it does not execute a candle provider or persistence query
