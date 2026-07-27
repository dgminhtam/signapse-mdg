## 1. Simplified Mapping Persistence

- [x] 1.1 Update `SymbolProviderMappingModel` to keep provider identity, the parent foreign key,
  `is_active`, and audit timestamps while removing equivalence, enablement, and capability-priority
  fields and constraints.
- [x] 1.2 Add Alembic revision `20260727_0018` after `20260727_0017` to add and backfill
  `is_active`, validate exactly one active mapping per supported symbol, create the partial unique
  index, and remove the superseded columns and constraints.
- [x] 1.3 Implement the `20260727_0018` downgrade so every mapping row is preserved while the
  removed `20260727_0017` fields and constraints are reconstructed deterministically.

## 2. Database Verification

- [x] 2.1 Update PostgreSQL integration coverage to verify the simplified schema, unchanged legacy
  columns, preserved provider values and timestamps, active mappings for disabled assets, and
  absence of equivalence, enablement, and priority columns.
- [x] 2.2 Add integration coverage proving multiple provider mappings can belong to one asset,
  duplicate mapping identities remain rejected, and the partial unique index rejects two active
  mappings for the same asset.
- [x] 2.3 Add incremental upgrade and downgrade coverage proving `20260727_0018` preserves mapping,
  supported-symbol, and candle rows.
- [x] 2.4 Run existing symbol, quote, candle, stream, backfill, and historical-price tests to
  confirm current runtime behavior remains unchanged.

## 3. Documentation

- [x] 3.1 Update system design, registry, and technology documentation to describe one asset-wide
  active provider mapping shared by all market-data routes and explicitly exclude fallback.
- [x] 3.2 Remove documentation for equivalence keys, mapping enablement, and route-specific
  priorities while retaining the expand/contract compatibility plan and provider-owned candle
  history.

## 4. Quality Checks

- [x] 4.1 Run PostgreSQL migration tests with `TEST_DATABASE_URL`, including fresh upgrade,
  incremental upgrade, and downgrade.
- [x] 4.2 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and
  `uv run mypy app`.
- [x] 4.3 Run strict OpenSpec validation for `simplify-symbol-provider-selection`.
