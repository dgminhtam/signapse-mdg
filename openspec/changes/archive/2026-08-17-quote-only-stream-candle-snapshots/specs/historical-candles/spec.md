# Historical Candles Specification Delta

## MODIFIED Requirements

### Requirement: Only complete candles are persisted

The gateway SHALL determine completion from the candle close time and gateway receive time, SHALL
apply the symbol's market-session policy before persistence, SHALL upsert eligible complete
candles using `(provider, provider_symbol, timeframe, open_time)`, and MUST NOT persist a forming
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
- **AND** it is not persisted as a complete candle

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
- **AND** the gateway uses those derived opens for persistence lookup, provider gap fill, forming
  snapshot merge, and response filtering

#### Scenario: Count request omits to

- **WHEN** a valid count request omits `to`
- **THEN** the gateway captures current UTC once and uses it as the exclusive upper boundary for
  count derivation, provider access, cache decisions, and response serialization

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

- **WHEN** a count request crosses weekends, holidays, maintenance breaks, or pandas calendar
  break windows
- **THEN** closed-session candle opens do not count toward `limit`
- **AND** no provider request is made for closed-session-only sections

#### Scenario: Count request encounters natural provider gaps

- **WHEN** a provider omits one or more derived eligible candle slots
- **THEN** the gateway returns the valid available candles, which can be fewer than `limit`
- **AND** it does not synthesize missing candles or issue provider-specific paging retries to force
  exactly `limit` rows

#### Scenario: Count request uses cached forming candle

- **WHEN** a current forming snapshot matches one of the derived eligible opens
- **THEN** the gateway can merge that candle into the response with `complete=false`
- **AND** it does not persist the forming candle

### Requirement: Forming candle cache is isolated by Provider Selection

The gateway MUST identify each process-local forming candle snapshot by canonical symbol, Provider
Identifier, provider symbol, and timeframe, and MUST record the gateway store time needed for TTL
evaluation. A request MAY reuse a forming snapshot only when it resolves to the same Provider
Mapping and the snapshot has not reached its close time or exceeded the configured forming-cache
TTL.

#### Scenario: Two mappings form the same canonical timeframe

- **WHEN** two Provider Mappings produce forming snapshots for the same canonical symbol and
  timeframe
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

## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Real-time candle events maintain current in-memory state

**Reason**: WebSocket candle events and their stream-owned forming state are removed.

**Migration**: The REST candle service owns forming snapshots through the process-local forming
snapshot cache and fills them through the selected candle provider.

### Requirement: Completed stream candles are persisted without blocking fanout

**Reason**: The quote-only WebSocket no longer emits or persists completed candle events.

**Migration**: Completed candles are persisted by the existing REST candle fill path; live quote
stream fanout remains independent of candle persistence.
