## MODIFIED Requirements

### Requirement: Real-time candle events maintain current in-memory state
The gateway SHALL maintain at most one current forming candle per canonical `(symbol, timeframe)`
from valid normalized WebSocket candle events that satisfy the symbol's market-session policy and
SHALL make that state available to the historical candle service.

#### Scenario: Forming candle update is received
- **WHEN** a valid stream candle has `complete=false`
- **AND** its open time is market-session eligible for that symbol and timeframe
- **THEN** it replaces the current in-memory candle for the same symbol and timeframe

#### Scenario: Session-ineligible forming candle update is received
- **WHEN** a stream candle has `complete=false`
- **AND** its open time is not market-session eligible for that symbol and timeframe
- **THEN** it is not stored as the current in-memory candle

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
repository boundary when the completed candle satisfies the symbol's market-session policy.
Persistence MUST NOT run inside the provider SDK callback or block live fanout.

#### Scenario: Stream candle closes
- **WHEN** a valid normalized stream candle has `complete=true`
- **AND** its open time is market-session eligible for that symbol and timeframe
- **THEN** it is removed from current forming state if it matches that series and open time
- **AND** it is enqueued for idempotent persistence
- **AND** matching downstream clients receive the completed candle without waiting for PostgreSQL

#### Scenario: Session-ineligible stream candle closes
- **WHEN** a normalized stream candle has `complete=true`
- **AND** its open time is not market-session eligible for that symbol and timeframe
- **THEN** it is not enqueued for persistence
- **AND** it is not exposed as a historical current or completed candle

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
