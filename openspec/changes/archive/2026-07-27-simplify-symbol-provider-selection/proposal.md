## Why

The current normalized-mapping design models provider equivalence and separate quote, candle, and
stream priorities even though the gateway only needs one selected provider per asset. Simplifying
the schema now avoids encoding unused fallback behavior before the database change is released.

## What Changes

- Keep the one-to-many relationship from `supported_symbols` to `symbol_provider_mappings`.
- Replace equivalence keys, mapping enablement, and capability-specific priorities with one
  `is_active` flag.
- Allow multiple configured provider mappings per asset while permitting at most one active
  mapping.
- Backfill each existing legacy provider mapping as the asset's active mapping.
- Define the active mapping as the single provider selection shared by quote, candle, and stream;
  no fallback or per-route provider selection is introduced.
- Retain the legacy provider columns during the database expansion phase so current runtime
  behavior remains compatible.
- Supersede the mapping-selection semantics proposed by `normalize-symbol-provider-mappings`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `supported-symbol-registry`: Simplify normalized provider mappings to one asset-wide active
  provider selection without equivalence groups, priorities, or fallback.

## Impact

- Adds a `20260727_0018` corrective migration and updates `SymbolProviderMappingModel`.
- Updates PostgreSQL migration and constraint coverage.
- Updates registry persistence documentation and OpenSpec requirements.
- Does not change public APIs, provider adapters, candle identity, or current route behavior.
- Can upgrade a database where `20260727_0017` has already been applied; no migration history is
  rewritten.
