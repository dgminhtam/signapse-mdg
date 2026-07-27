## Why

Provider routing is duplicated between the normalized `symbol_provider_mappings` table and legacy
columns on `supported_symbols`, while the runtime still reads the legacy copy. This prevents the
normalized active mapping from being the source of truth and requires fragile dual writes whenever
a provider selection changes.

## What Changes

- Resolve every enabled runtime symbol by joining it to its single active
  `symbol_provider_mappings` row.
- Route quote, candle, WebSocket, and candle-backfill work through that resolved active mapping
  without fallback to inactive mappings.
- Fail closed when an enabled symbol has no active provider mapping instead of silently omitting or
  misrouting it.
- Preserve the existing `SupportedSymbol` runtime shape and `GET /v1/symbols` response shape, with
  provider fields populated from the active mapping.
- Remove the legacy `supported_symbols.provider` and `supported_symbols.provider_symbol` columns
  and their uniqueness constraint after the new runtime has been deployed.
- Preserve provider identity on historical candle rows; changing the active mapping affects future
  routing and does not relabel existing candles.
- Provide a reversible contract migration that reconstructs legacy columns from active mappings
  when downgrading.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `supported-symbol-registry`: Make the normalized active mapping authoritative for runtime reads,
  remove the legacy provider columns, preserve the public symbol response, and define fail-closed
  and reversible migration behavior.
- `latest-quotes`: Resolve quote routing from the single active normalized provider mapping.
- `historical-candles`: Resolve candle reads and provider fills from the active mapping while
  retaining historical provider ownership.
- `market-data-websocket-stream`: Resolve every stream interest from the active mapping shared with
  HTTP market-data routes.
- `candle-backfill`: Resolve provider filtering and fills from each enabled symbol's active mapping.

## Impact

- Database schema and Alembic migration after revision `20260727_0019`.
- SQLAlchemy supported-symbol models and PostgreSQL symbol/candle repositories.
- Quote, candle, WebSocket, and backfill routing inputs, without changing provider adapter
  interfaces.
- Registry and migration integration tests, plus routing regression tests.
- `docs/spec.md`, `docs/system-design.md`, and `docs/tech-stack.md`.
- No new dependency and no public HTTP or WebSocket response-shape change.
