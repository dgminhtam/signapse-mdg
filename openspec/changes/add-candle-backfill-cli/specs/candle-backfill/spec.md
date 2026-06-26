## ADDED Requirements

### Requirement: Candle backfill can be run from an internal CLI
The gateway SHALL provide an internal command-line entry point for backfilling historical candles
into `market_data_candles` for a supplied UTC half-open time range and one or more supported
timeframes.

#### Scenario: Backfill command is invoked with a valid scope
- **WHEN** an operator runs the backfill command with `from`, `to`, and supported timeframe values
- **THEN** the command processes the requested historical candle scope
- **AND** it does not expose a new public HTTP or WebSocket API

#### Scenario: Backfill command receives an unsupported timeframe
- **WHEN** an operator includes an unsupported timeframe
- **THEN** the command rejects the invocation before provider access
- **AND** no candle rows are written

### Requirement: Backfill scope uses the enabled symbol registry
The backfill command SHALL select symbols from the PostgreSQL-backed enabled symbol registry and
MUST route provider fills using each symbol's persisted `provider` and `provider_symbol` mapping.

#### Scenario: Backfill runs without explicit symbol filters
- **WHEN** the command is run for all enabled symbols
- **THEN** it considers enabled registry rows as the backfill universe
- **AND** disabled or absent symbols are not processed

#### Scenario: Backfill runs with explicit symbol filters
- **WHEN** the command is run with a subset of canonical symbols
- **THEN** it processes only matching enabled registry rows
- **AND** it rejects unknown or disabled symbols before provider access

### Requirement: Backfill reuses repository-first gap filling
Backfill SHALL reuse the gateway candle flow that loads persisted complete candles, identifies
missing eligible opens, fetches only missing provider ranges, applies market-session policy, and
upserts complete candles idempotently.

#### Scenario: Requested chunk is fully persisted
- **WHEN** every eligible candle open in a backfill chunk already exists as a complete persisted row
- **THEN** no provider candle request is made for that chunk

#### Scenario: Requested chunk has missing eligible candles
- **WHEN** one or more eligible candle opens are absent from persistence
- **THEN** the command requests only provider windows covering those missing sections
- **AND** complete eligible fetched candles are upserted into `market_data_candles`

#### Scenario: Provider returns forming or session-ineligible candles
- **WHEN** a provider response includes a forming candle or a candle outside the symbol's
  market-session policy
- **THEN** that candle is not persisted by the backfill run

### Requirement: Backfill chunks long ranges
The backfill command SHALL split requested ranges into bounded chunks before calling the candle
service and MUST NOT bypass `MAX_CANDLES_PER_REQUEST`.

#### Scenario: Requested range exceeds one chunk
- **WHEN** a requested symbol and timeframe range contains more scheduled candles than the
  configured per-request maximum
- **THEN** the command processes the range as multiple half-open chunks
- **AND** each chunk stays within the configured candle-count bound

#### Scenario: Backfill is rerun for the same range
- **WHEN** the same backfill scope is run again after complete candles were persisted
- **THEN** existing complete rows are reused
- **AND** duplicate candle rows are not created

### Requirement: Backfill reports bounded failures
The backfill command SHALL report provider, registry, and persistence failures with the affected
symbol, timeframe, and chunk boundaries without exposing credentials, SQL, raw provider payloads,
or stack traces.

#### Scenario: One chunk fails
- **WHEN** a provider or database failure occurs for a chunk
- **THEN** the command reports the failed chunk
- **AND** previously persisted complete candles remain valid for later reruns

#### Scenario: Any chunk fails during the run
- **WHEN** one or more chunks fail
- **THEN** the command exits with a non-zero status
