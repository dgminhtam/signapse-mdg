## ADDED Requirements

### Requirement: Provider-backed count scans Eligible Candle Slots lazily

The gateway SHALL execute a provider-backed candle `count` query through bounded, directional
pages of Eligible Candle Slots and SHALL NOT materialize the entire Candle Count Scan Budget before
attempting to resolve the requested Provider-backed Candle Snapshots.  The first page SHALL contain
no more slots than both the requested Candle Count and the configured page capacity; subsequent
pages SHALL be created only while the requested Candle Count remains unsatisfied and the Candle
Count Scan Budget remains.

#### Scenario: Initial count page is bounded by the requested count
- **WHEN** a client requests a valid provider-backed count smaller than the configured page capacity
- **THEN** the gateway derives no more than that Candle Count of Eligible Candle Slots for the
  initial page
- **AND** it does not derive later pages unless the initial page cannot satisfy the Candle Count

#### Scenario: Sparse count advances only as needed
- **WHEN** a count page contains fewer Provider-backed Candle Snapshots than the requested Candle
  Count because eligible slots are absent from persistence and the selected provider
- **THEN** the gateway derives the next directional page within the remaining Candle Count Scan
  Budget
- **AND** it stops deriving pages as soon as it has accumulated the requested number of unique
  Provider-backed Candle Snapshots

#### Scenario: Calendar-backed count preserves session eligibility
- **WHEN** a provider-backed count query crosses a holiday, early close, session break, DST
  transition, or configured provider schedule offset
- **THEN** its lazily derived Eligible Candle Slots preserve the symbol's market-session policy and
  candle-schedule semantics
- **AND** closed-session slots do not consume the Candle Count Scan Budget

### Requirement: Incomplete provider-backed count pages use one logical contiguous fill

For an incomplete provider-backed count page, the gateway SHALL request one logical contiguous
Candle History Window from the immutable Provider Selection and SHALL filter normalized provider
rows back to the page's Eligible Candle Slots before merging.  A selected provider adapter MAY
internally chunk or page that logical window to honor provider-native limits.

#### Scenario: Fully persisted count page avoids provider access
- **WHEN** every Eligible Candle Slot in a count page has a persisted complete candle
- **THEN** the gateway returns those canonical persisted candles for the page
- **AND** it makes no provider candle request for that page

#### Scenario: Partially persisted count page uses a contiguous logical fill
- **WHEN** one or more Eligible Candle Slots in a count page are absent from complete persistence
- **THEN** the gateway requests one logical contiguous Candle History Window from the selected
  Provider Selection for that page
- **AND** it may receive rows already present in persistence
- **AND** it filters, canonicalizes, and persists valid completed rows without changing the
  Provider Selection

#### Scenario: Contiguous count fill crosses a closed interval safely
- **WHEN** a count page's Candle History Window spans an overnight, weekend, holiday, or configured
  session break
- **THEN** the gateway may include that closed interval in the logical provider request
- **AND** it returns only rows whose open times are Eligible Candle Slots in the page
- **AND** it does not create a provider request for a page containing no Eligible Candle Slots

## MODIFIED Requirements

### Requirement: Closed candles are reused from PostgreSQL

The gateway SHALL query persisted complete candles before calling the selected provider, SHALL
discard candles that violate the symbol's market-session policy, and SHALL identify expected opens
using the symbol's provider/market candle schedule.  For exact-range and slot-based `limit`
requests, the gateway SHALL identify missing expected opens and request provider windows covering
only their missing sections.  For a provider-backed `count` page, the gateway SHALL first query
persisted complete candles for that page and, when the page remains incomplete, SHALL use the
count-page contiguous-fill behavior.

#### Scenario: Complete eligible range is persisted

- **WHEN** every expected eligible candle open is available as a persisted complete candle
- **THEN** the gateway returns the persisted candles
- **AND** it makes no provider candle request

#### Scenario: Part of an exact-range or slot-based eligible range is missing

- **WHEN** one or more expected eligible opens are absent from persistence for an exact-range or
  slot-based `limit` request
- **THEN** the gateway requests only provider windows covering those missing sections from the
  symbol's persisted mapping
- **AND** it merges valid fetched candles with eligible persisted candles by open time

#### Scenario: Provider schedule is offset from UTC epoch

- **WHEN** a provider labels hourly candles at minute thirty
- **THEN** gap detection uses that schedule and recognizes persisted minute-thirty rows

#### Scenario: Provider omits an expected eligible slot

- **WHEN** the selected provider returns no candle for an expected eligible missing slot
- **THEN** the gateway returns the valid available candles after the fill attempt
- **AND** it does not synthesize an OHLCV candle

### Requirement: Historical candles can be requested by provider-backed candle count

The gateway SHALL allow `GET /v1/candles` clients to request up to `count` unique
Provider-backed Candle Snapshots. A result MAY contain fewer snapshots when history is exhausted,
provider or session gaps leave rows absent, or the internal scan budget is reached. The gateway
MUST NOT create synthetic candles to satisfy `count`.  The gateway SHALL accumulate snapshots from
lazy Eligible Candle Slot pages until the Candle Count is reached, history is exhausted, or the
Candle Count Scan Budget is reached.

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

#### Scenario: Provider-backed count preserves response shape, order, and scan boundaries

- **WHEN** a valid provider-backed count query returns one or more snapshots
- **THEN** the response contains only `symbol`, `timeframe`, `from`, `to`, and `candles` at the top
  level
- **AND** the candle list is sorted by `openTime` ascending
- **AND** the response boundaries describe the resolved Candle History Window actually scanned,
  rather than inferred data extents or unused page capacity

#### Scenario: Provider failure does not become a count partial result

- **WHEN** a selected provider fails while resolving a later provider-backed count page after one
  or more earlier pages supplied valid snapshots
- **THEN** the gateway preserves the existing sanitized provider-failure response
- **AND** it does not convert the operational failure into a successful partial count response

#### Scenario: Provider-backed count is provider-agnostic

- **WHEN** the same count mode is requested for any candle-capable selected Provider Selection
- **THEN** the gateway applies the same row-count, gap, cutoff, ordering, and response semantics
- **AND** it does not silently switch to another Provider Mapping
