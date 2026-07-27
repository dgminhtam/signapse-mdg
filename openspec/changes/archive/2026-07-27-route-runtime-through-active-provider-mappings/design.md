## Context

`supported_symbols` currently owns canonical asset metadata and duplicates the selected upstream
identity in legacy `provider` and `provider_symbol` columns. Revisions `20260727_0017` through
`20260727_0019` introduced and populated `symbol_provider_mappings`, including one `is_active`
mapping per asset, but runtime repositories still build `SupportedSymbol` from the legacy columns.

Quote, candle, WebSocket, and backfill paths already consume the same flat `SupportedSymbol`
domain object. The remaining cutover is therefore concentrated at the repository boundary, after
which the duplicated columns can be removed. Historical candles must retain their recorded provider
identity because a later provider switch must not relabel or merge provider-owned history.

Dropping the legacy columns before every deployed runtime stops reading them would break rolling
deployments. The cutover and schema contraction therefore require separate deployment gates.

## Goals / Non-Goals

**Goals:**

- Make the single active normalized mapping authoritative for all runtime market-data routing.
- Fail closed when an enabled canonical symbol lacks an active mapping.
- Preserve current provider adapters, the flat `SupportedSymbol` runtime object, and public response
  shapes.
- Remove the duplicated provider columns and constraint from `supported_symbols`.
- Preserve historical candle identity and make the contraction migration reversible.
- Support a rollout in which runtime readers are migrated before legacy storage is dropped.

**Non-Goals:**

- No automatic provider fallback, aggregation, health-based selection, or per-route mapping.
- No provider-selection administration API.
- No rewrite or deletion of existing `market_data_candles`.
- No removal of provider identity from domain objects, provider adapters, candle rows, or the
  existing `GET /v1/symbols` response.
- No trigger enforcing at least one active child mapping.
- No edits to historical Alembic revisions `0001` through `0019`.

## Decisions

### Resolve the active mapping at the repository boundary

Both enabled-symbol repository queries will join `supported_symbols` to
`symbol_provider_mappings` on `supported_symbol_id` and `is_active`. They will construct the
existing `SupportedSymbol` object from canonical metadata plus the joined provider values.

This keeps quote, candle, stream, and backfill services unchanged because they already share that
resolved object. Introducing a second runtime mapping object or teaching every service to query the
mapping table would duplicate selection logic.

### Use an outer join and fail closed on a missing active mapping

The database partial unique index prevents more than one active mapping but cannot require at least
one child row without a trigger. Repository reads will use an outer join so an enabled symbol with
no active mapping remains observable and causes `DatabaseUnavailableError`.

An inner join was rejected because it would silently omit a misconfigured enabled symbol and make
it appear unsupported. A database trigger was rejected because the registry has no runtime write
API and repository validation plus migration checks provide the required boundary with less
operational complexity.

### Keep `SupportedSymbol` flat and preserve the symbol API

`SupportedSymbol.provider` and `SupportedSymbol.provider_symbol` remain resolved runtime values,
not persisted columns of the canonical table. `GET /v1/symbols` continues returning `provider` and
`providerSymbol`, populated from the active mapping.

Removing or nesting those fields was rejected because it would create a breaking API change and
force broad adapter churn without improving selection integrity.

### Keep candle provider identity independent from the active mapping

`market_data_candles` continues using
`(provider, provider_symbol, timeframe, open_time)` as provider-owned identity. Repository reads for
a request use the currently resolved active mapping; switching the active mapping starts a separate
history and does not update old rows.

Adding a mapping foreign key or rewriting old candle rows was rejected because historical mappings
may become inactive or be removed while their market data remains valid.

### Contract the schema only after runtime cutover

The contract revision following `20260727_0019` will:

1. validate exactly one active mapping for every canonical symbol;
2. drop `uq_supported_symbols_provider_symbol`;
3. drop `supported_symbols.provider_symbol`;
4. drop `supported_symbols.provider`.

Historical migrations remain unchanged so a fresh database can replay their legacy writes before
the contract revision removes the columns.

### Reconstruct legacy storage from active mappings on downgrade

Downgrade will add nullable legacy columns, fill them from each active mapping, validate completeness
and uniqueness, make them non-null, and recreate the legacy unique constraint. It will fail rather
than guess if a canonical symbol has no active mapping.

This produces a schema usable by the previous runtime and preserves the provider selection current
at downgrade time without maintaining a permanent mirror.

## Risks / Trade-offs

- Old runtime instances break after the contract migration → deploy and verify the active-mapping
  runtime everywhere before applying the column-drop revision.
- An enabled symbol can lose its only active mapping through direct SQL → use a transaction for
  switches and make repository reads fail with the sanitized database-unavailable boundary.
- A provider switch changes which candle history is returned → retain provider-owned histories and
  document that a new active provider starts a separate series.
- Downgrade depends on complete active mappings → validate before schema mutation and abort without
  partial DDL when the invariant is violated.
- Tests tied to legacy columns may accidentally be deleted wholesale → retain revision-scoped
  migration tests and update only head-schema/runtime expectations.

## Migration Plan

1. Confirm revision `20260727_0019` has exactly one active mapping for every supported symbol.
2. Deploy the repository cutover while the legacy columns still exist.
3. Verify symbol listing, quote, candle, stream, and backfill routes use active mappings even when a
   legacy value differs in a controlled test.
4. Confirm no deployed application version reads the legacy columns.
5. Apply the contract migration that validates active mappings and drops the legacy storage.
6. Verify the head schema, all 24 active defaults, five inactive alternatives, unchanged public
   response shapes, and unchanged candle rows.
7. Roll back by downgrading first, which reconstructs legacy values from active mappings, and only
   then deploying the previous runtime.

## Open Questions

None.
