## Why

The supported-symbol registry currently stores one provider and provider symbol directly on each
canonical asset, so PostgreSQL cannot represent multiple provider mappings without duplicating the
canonical symbol. The database needs a backward-compatible normalized mapping layer before quote,
candle, or stream fallback can be designed safely.

## What Changes

- Add a `symbol_provider_mappings` table that stores provider identity, provider symbol,
  equivalence key, enabled state, and nullable quote, candle, and stream priorities for each
  canonical supported symbol.
- Backfill every existing `supported_symbols` provider mapping into the new table as the sole
  priority-zero mapping for all three market-data capabilities.
- Keep the existing `supported_symbols.provider` and `supported_symbols.provider_symbol` columns
  during this expand-only change so the deployed application remains compatible.
- Add database constraints that reject duplicate provider mappings, ambiguous per-capability
  priorities, negative priorities, empty mapping identifiers, and mappings with no capability.
- Add SQLAlchemy metadata and migration coverage for fresh install, upgrade, constraint
  enforcement, and downgrade.
- Do not add secondary mappings or change provider routing, fallback behavior, candle persistence,
  or public API responses in this change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `supported-symbol-registry`: Normalize persisted provider mappings into a child table while
  preserving the legacy single-provider columns during a backward-compatible expansion phase.

## Impact

- Affected code: Alembic migration chain, SQLAlchemy database models, supported-symbol registry
  integration tests, and database design documentation.
- Database: adds one table and copies existing mapping data without modifying or deleting current
  registry rows or candle history.
- Public APIs: no response or request changes.
- Provider behavior: no routing or fallback changes.
- Dependencies: no new dependency.
