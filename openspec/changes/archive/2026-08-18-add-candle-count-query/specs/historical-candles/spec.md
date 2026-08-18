## MODIFIED Requirements

### Requirement: Candle requests are bounded
The gateway SHALL reject an exact-range or slot-based request that exceeds
`MAX_CANDLES_PER_REQUEST`, with a default of 1,000 expected candles or eligible slots. A
provider-backed `count` request SHALL accept values from 1 through 1,000. Count-mode scanning SHALL
also be bounded by a separate internal maximum number of eligible slots inspected.

#### Scenario: Expected candle count is too large
- **WHEN** either the conservative or exact scheduled count for an exact-range request exceeds
  `MAX_CANDLES_PER_REQUEST`
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

### Requirement: Historical candles can be requested by eligible count

The gateway SHALL allow `GET /v1/candles` clients to request the latest eligible candle slots using
`limit` instead of `from`. This `limit` mode SHALL count eligible timeframe slots rather than
provider-backed rows. The request SHALL be self-contained and MUST NOT require an active WebSocket
quote subscription. For `limit=1`, the gateway SHALL return the latest eligible available candle:
a valid forming snapshot when available, otherwise the latest completed candle; when neither is
available it SHALL return an empty `candles` array.

#### Scenario: Slot-limit request resolves latest eligible opens

- **WHEN** a client requests an enabled canonical symbol, supported timeframe, valid `limit`, and
  no `from`
- **THEN** the gateway derives the latest `limit` eligible candle opens at or before the resolved
  `to` boundary using the symbol's candle schedule and market-session policy
- **AND** the gateway uses those derived opens for persistence lookup, provider gap fill, cache
  forming snapshot merge, and response filtering

#### Scenario: Slot-limit request omits to

- **WHEN** a valid slot-limit request omits `to`
- **THEN** the gateway captures current UTC once and uses it as the exclusive upper boundary for
  slot derivation, provider access, and response serialization

#### Scenario: Candle request works without an active WebSocket

- **WHEN** a client requests a valid latest slot-limit candle query without any active quote stream
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

#### Scenario: Slot-limit request crosses closed sessions

- **WHEN** a slot-limit request crosses weekends, holidays, maintenance breaks, or pandas calendar
  break windows
- **THEN** closed-session candle opens do not count toward `limit`
- **AND** no provider request is made for closed-session-only sections

#### Scenario: Slot-limit request encounters natural provider gaps

- **WHEN** a provider omits one or more derived eligible candle slots
- **THEN** the gateway returns the valid available candles, which can be fewer than `limit`
- **AND** it does not synthesize missing candles or issue provider-specific paging retries to force
  exactly `limit` rows

#### Scenario: Slot-limit request uses cached forming candle

- **WHEN** a current cached forming candle matches one of the derived eligible opens
- **THEN** the gateway can merge that candle into the response with `complete=false`
- **AND** it does not persist the forming candle

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

## ADDED Requirements

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
