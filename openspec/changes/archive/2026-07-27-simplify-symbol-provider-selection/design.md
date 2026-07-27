## Context

Revision `20260727_0017` introduces `symbol_provider_mappings` as a child of `supported_symbols`, but models
provider equivalence, independent route priorities, and mapping enablement. The intended product
behavior is narrower: an asset may have several configured provider mappings, while one active
mapping supplies quote, candle, and stream data. There is no automatic fallback.

The existing application still reads `supported_symbols.provider` and
`supported_symbols.provider_symbol`, so this remains a database-first expansion.

## Goals / Non-Goals

**Goals:**

- Preserve the one-to-many asset-to-provider-mapping relationship.
- Represent one asset-wide provider selection with `is_active`.
- Preserve existing mappings and legacy runtime compatibility.
- Make the corrective migration safe after `20260727_0017` has been applied.

**Non-Goals:**

- No fallback, aggregation, equivalence grouping, or provider priority.
- No different provider selection for quote, candle, and stream.
- No provider-switching API or runtime repository change.
- No legacy-column removal or candle migration.

## Decisions

### Replace route-specific selection fields with `is_active`

`symbol_provider_mappings` will contain:

- `id`;
- `supported_symbol_id`;
- `provider`;
- `provider_symbol`;
- `is_active`;
- `created_at`;
- `updated_at`.

`equivalence_key`, `enabled`, `quote_priority`, `candle_priority`, and `stream_priority` will be
removed. A mapping row is configured and available for manual selection by definition;
`supported_symbols.enabled` remains the asset availability switch.

The parent foreign key already establishes that mappings describe the same canonical asset.
Adding equivalence groups or per-capability priorities without fallback would duplicate meaning
and create unused states.

### Enforce at most one active mapping with a partial unique index

A unique PostgreSQL index on `supported_symbol_id WHERE is_active` prevents two active mappings
for one asset. Ordinary constraints cannot require at least one active child row without a trigger,
so the migration validates current data and a later runtime repository must fail closed if an
asset has no active mapping.

Alternative considered: store `active_provider_mapping_id` on `supported_symbols`. Rejected
because it introduces a circular foreign-key lifecycle and requires extra integrity enforcement to
prove that the selected mapping belongs to the same asset.

### Use a new corrective migration

Revision `20260727_0018` will transform the table created by `20260727_0017` rather than rewriting migration
history. It will:

1. add `is_active` with default `false`;
2. mark the enabled mapping whose three priorities are all zero as active;
3. validate exactly one active mapping for every supported symbol;
4. create the partial unique index;
5. remove the superseded constraints and columns.

This handles both fresh migration replay and databases where `0017` is already installed.

### Keep one provider selection for all market-data routes

When runtime routing is changed later, the symbol repository will join the one active mapping and
continue returning the existing `SupportedSymbol(provider, provider_symbol)` domain object.
Quote, candle, and stream routers already consume that same object, so no route-specific selection
model is needed.

Switching providers will be an explicit transaction that deactivates the current mapping and
activates another mapping belonging to the same asset. No request-time fallback occurs.

### Preserve provider-owned candle history

`market_data_candles` remains identified by
`(provider, provider_symbol, timeframe, open_time)`. Switching the active provider affects future
requests and writes but does not rewrite historical candle ownership.

## Risks / Trade-offs

- An asset can temporarily have no active mapping through direct SQL → migration validation and a
  later repository fail-closed check prevent silent provider selection.
- Existing `20260727_0017` data may encode different priority-zero providers per capability →
  `20260727_0018` fails
  instead of guessing unless exactly one enabled mapping is priority zero for all three routes.
- Legacy and normalized provider values can drift during the expansion window → keep registry
  writes paused until runtime routing moves to the active mapping.
- Downgrade must recreate removed `20260727_0017` columns → assign active mapping priority zero and
  deterministic positive priorities to inactive mappings; current runtime still ignores them.

## Migration Plan

1. Apply `20260727_0017` if it is not already present.
2. Apply `20260727_0018`, validate one active mapping per supported symbol, and simplify the table.
3. Deploy without changing runtime routing.
4. In a later change, route all three market-data paths through the active mapping.
5. Remove legacy provider columns only after all deployed application versions stop reading them.

Downgrade recreates the `20260727_0017` columns and constraints without deleting mapping rows, then removes
the active-selection index and column.

## Open Questions

None. Provider switching and runtime cutover belong to later changes.
