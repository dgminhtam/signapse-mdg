## ADDED Requirements

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

