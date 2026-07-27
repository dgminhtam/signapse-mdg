## 1. Active-Mapping Repository Cutover

- [x] 1.1 Add integration coverage proving enabled-symbol listing and single-symbol lookup resolve
  provider values from the active normalized mapping even when legacy columns differ.
- [x] 1.2 Update both PostgreSQL symbol lookup paths to join the single active
  `SymbolProviderMappingModel` row and construct the existing flat `SupportedSymbol` value.
- [x] 1.3 Make enabled symbols without an active mapping raise `DatabaseUnavailableError` instead
  of being omitted or treated as unsupported.
- [x] 1.4 Add regression coverage proving inactive mappings are ignored and a transactional active
  mapping switch changes subsequent repository reads.

## 2. Market-Data Routing Verification

- [x] 2.1 Update quote integration tests to prove provider refresh grouping uses resolved active
  mappings and never falls back to inactive mappings.
- [x] 2.2 Update candle integration tests to prove reads and provider fills use the active mapping
  while existing provider-owned candle rows remain unchanged after a switch.
- [x] 2.3 Update WebSocket routing tests to prove new interests use the active mapping shared by
  HTTP routes and unsupported active providers preserve the sanitized failure boundary.
- [x] 2.4 Update backfill tests to prove provider filters and fills use resolved active mappings and
  missing active mappings fail before provider access.
- [x] 2.5 Confirm the existing `GET /v1/symbols` response shape is unchanged and its provider fields
  come from the active mapping.

## 3. Legacy-Column Contract Migration

- [x] 3.1 Add the Alembic revision after `20260727_0019` that validates exactly one active mapping
  per canonical symbol before changing the schema.
- [x] 3.2 In the upgrade, drop `uq_supported_symbols_provider_symbol` and the legacy
  `supported_symbols.provider_symbol` and `supported_symbols.provider` columns without changing
  normalized mappings or candle rows.
- [x] 3.3 In the downgrade, recreate nullable legacy columns, backfill them from active mappings,
  validate completeness and uniqueness, restore non-nullability, and recreate the uniqueness
  constraint.
- [x] 3.4 Remove the two legacy fields and constraint from `SupportedSymbolModel` while retaining
  provider fields on `SymbolProviderMappingModel`, domain `SupportedSymbol`, API DTOs, and candle
  persistence.

## 4. Migration and Schema Regression Coverage

- [x] 4.1 Update head-schema tests to assert the legacy supported-symbol columns and constraint are
  absent while normalized mapping constraints remain present.
- [x] 4.2 Add upgrade tests proving contraction aborts atomically when any canonical symbol lacks
  an active mapping and succeeds without changing the 29 approved mappings or existing candles.
- [x] 4.3 Add downgrade tests proving legacy values are reconstructed from the current active
  mappings and the previous runtime schema is usable.
- [x] 4.4 Preserve revision-scoped tests for historical migrations `0017` through `0019`, updating
  only tests whose expectations apply to the new head schema.
- [x] 4.5 Verify a fresh migration chain through the new head succeeds and repeated
  upgrade/downgrade coverage leaves registry and candle data intact.

## 5. Documentation and Validation

- [x] 5.1 Update `docs/spec.md`, `docs/system-design.md`, and `docs/tech-stack.md` so
  `symbol_provider_mappings` is the sole routing source and provider switching no longer requires
  legacy mirror writes.
- [x] 5.2 Document the deployment gate: run the active-mapping runtime on revision `0019`, verify
  all instances have cut over, then apply the contract migration; rollback the database before
  deploying legacy runtime code.
- [x] 5.3 Run focused unit and integration tests for registry, quote, candle, stream, backfill, and
  migration behavior.
- [x] 5.4 Run `uv run pytest`, `uv run ruff check .`, `uv run mypy app`, and strict OpenSpec
  validation.
