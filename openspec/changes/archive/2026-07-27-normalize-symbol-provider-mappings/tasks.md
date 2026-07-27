## 1. Mapping Persistence

- [x] 1.1 Add standalone `SymbolProviderMappingModel` SQLAlchemy metadata with the normalized
  columns, foreign key, uniqueness constraints, check constraints, and audit timestamps.
- [x] 1.2 Add Alembic revision `0017` after `20260727_0016` to create
  `symbol_provider_mappings`, backfill one priority-zero mapping per legacy registry row, validate
  the copied data, and drop only the new table on downgrade.

## 2. Database Verification

- [x] 2.1 Extend PostgreSQL integration coverage to verify fresh migration schema, unchanged legacy
  columns, preserved provider values, disabled-symbol handling, mapping count, priority values,
  equivalence keys, and absence of secondary mappings.
- [x] 2.2 Add focused integration checks proving duplicate mapping identities, duplicate
  per-symbol providers, duplicate capability priorities, negative priorities, missing
  capabilities, and blank identifiers are rejected.
- [x] 2.3 Add integration coverage for foreign-key cascade and `0017` downgrade back to
  `20260727_0016` without loss or reconstruction of legacy provider data.
- [x] 2.4 Run the existing symbol, quote, candle, stream, backfill, and historical-price tests to
  confirm the expand-only schema does not change runtime behavior.

## 3. Documentation

- [x] 3.1 Update `docs/system-design.md` with the normalized mapping schema, expand/contract rollout,
  preserved candle identity, and temporary legacy-column compatibility window.
- [x] 3.2 Update relevant registry and technology documentation to state that this change adds no
  secondary mapping or provider fallback behavior.

## 4. Quality Checks

- [x] 4.1 Run PostgreSQL integration tests with `TEST_DATABASE_URL`, including fresh upgrade and
  downgrade coverage.
- [x] 4.2 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and
  `uv run mypy app`.
- [x] 4.3 Run strict OpenSpec validation for `normalize-symbol-provider-mappings`.
