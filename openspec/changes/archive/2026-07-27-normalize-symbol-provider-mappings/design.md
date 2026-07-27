## Context

`supported_symbols` is both the canonical asset catalog and the provider-routing table. Its unique
`symbol` column permits one canonical row, while its `provider` and `provider_symbol` columns permit
only one upstream mapping for that row. Quote, candle, and stream services still read those legacy
columns directly.

The immediate requirement is database preparation, not runtime failover. The migration must
therefore support the current application version, preserve all existing registry and candle data,
and leave public API behavior unchanged.

## Goals / Non-Goals

**Goals:**

- Introduce a normalized one-to-many provider-mapping table.
- Preserve every current mapping as one enabled priority-zero quote, candle, and stream mapping.
- Enforce deterministic mapping identity and per-capability priority at the database boundary.
- Make the migration safe for a database-first deployment and simple to downgrade.
- Keep SQLAlchemy metadata aligned with the migrated schema.

**Non-Goals:**

- No secondary provider mappings.
- No quote, candle, or stream fallback.
- No repository or service routing change.
- No removal of the legacy provider columns.
- No change to the supported-symbol HTTP response.
- No `market_data_candles` schema or data migration.
- No synchronization trigger or registry administration API.

## Decisions

### Use an expand-only migration

Create `symbol_provider_mappings` and retain `supported_symbols.provider` and
`supported_symbols.provider_symbol`. Existing application instances can continue reading the
legacy columns while the new table is deployed.

Alternative considered: move the columns and drop them in one migration. Rejected because a
database-first deployment would break the currently deployed application before routing code can
be updated.

### Store capability order on each mapping

Each mapping has nullable `quote_priority`, `candle_priority`, and `stream_priority` small integers.
A null value means that the mapping is not eligible for that capability. Non-null priorities must
be non-negative and unique per canonical symbol and capability.

This is smaller than introducing separate capability and priority tables while still allowing a
later change to choose different provider orders for quote, candle, and stream behavior.

Alternative considered: one shared priority plus three support booleans. Rejected because it
cannot represent a provider that is primary for one capability and secondary for another.

### Keep equivalence explicit and fail closed

Every mapping stores a non-empty `equivalence_key`. Existing mappings are backfilled with the
opaque value `mapping:<supported_symbol_id>`, so no two existing assets or future provider rows are
implicitly declared interchangeable. A later provider-routing change must deliberately assign a
shared semantic key before enabling fallback.

Alternative considered: default the key to the canonical symbol. Rejected because current
canonical assets can represent futures or rolling-futures proxies, and equal display symbols do not
prove equivalent upstream instruments.

### Backfill one enabled priority-zero mapping per registry row

The migration copies every current registry row, including disabled canonical symbols, into one
enabled mapping with quote, candle, and stream priority `0`. Canonical `enabled` remains the asset
availability switch; mapping `enabled` independently controls whether a provider mapping can be
used after later routing changes.

The mapping inherits the registry row's creation and update timestamps. Migration validation
compares row counts and verifies one priority-zero mapping for every canonical row before
completion.

### Enforce mapping integrity with ordinary constraints

The table uses:

- a cascading foreign key to `supported_symbols.id`;
- unique `(supported_symbol_id, provider)`;
- unique `(provider, provider_symbol)`;
- unique `(supported_symbol_id, <capability>_priority)` for each capability;
- checks for non-empty provider, provider symbol, and equivalence key;
- checks for non-negative priorities and at least one non-null capability priority.

PostgreSQL unique constraints already create the indexes required for the current catalog size, so
the change adds no speculative secondary index. It also adds no trigger requiring every enabled
canonical symbol to retain a priority-zero mapping; cross-row routing completeness belongs to the
later repository boundary.

### Leave candle persistence provider-owned

`market_data_candles` continues to identify rows by
`(provider, provider_symbol, timeframe, open_time)`. The change does not add a mapping foreign key
because historical candles may belong to provider mappings no longer present in the active
registry, including retained Binance rows after crypto moved to Twelve Data.

Alternative considered: add `provider_mapping_id` to candle rows. Rejected because it requires
backfilling or inventing inactive mappings for historical provider identities without enabling any
new behavior.

### Add standalone SQLAlchemy metadata only

Add `SymbolProviderMappingModel` with the table columns and constraints, but do not change
repositories to load it and do not add an ORM relationship that can introduce accidental lazy
loads. Routing-oriented domain objects and repository queries belong to the later runtime change.

## Risks / Trade-offs

- Legacy columns and the new table can drift during the compatibility window → Do not make mapping
  data changes between this migration and the runtime-routing change; the service currently has no
  registry write API, so a synchronization trigger is unnecessary.
- Capability priority zero is copied from current behavior without revalidating provider coverage
  → This migration preserves configuration only; later routing work must audit capabilities before
  adding secondary rows.
- A database constraint can enforce at most one priority zero but not at least one per enabled
  canonical symbol without a trigger → Validate current data in the migration and make later
  repositories fail closed on incomplete routing data.
- Future fresh installs replay legacy seed migrations before normalization → The new migration
  runs after revision `20260727_0016`, copies the fully seeded catalog, and becomes the only place
  that creates normalized rows for those legacy seeds.

## Migration Plan

1. Add Alembic revision `0017` after `20260727_0016`.
2. Create `symbol_provider_mappings` with its foreign key, uniqueness, and check constraints.
3. Insert one mapping for every `supported_symbols` row using `INSERT ... SELECT`.
4. Validate mapping count and priority-zero coverage inside the migration transaction.
5. Add matching `SymbolProviderMappingModel` metadata.
6. Run fresh-upgrade, incremental-upgrade, constraint, and downgrade integration tests.
7. Deploy without changing application routing.

Rollback drops only `symbol_provider_mappings`. The untouched legacy columns remain authoritative,
so the current application continues to work after downgrade.

## Open Questions

None for this expand-only change. Provider equivalence assignments, secondary mapping seeds, and
legacy-column removal require later changes.
