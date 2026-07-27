## MODIFIED Requirements

### Requirement: Supported symbols are persisted

The gateway SHALL store canonical supported symbols in PostgreSQL with a unique canonical symbol,
an enabled state, display and calendar metadata, and audit timestamps. The gateway SHALL also
store normalized provider mappings in `symbol_provider_mappings`, with each mapping referencing one
canonical supported symbol and defining provider identity, provider symbol, active-selection
state, and audit timestamps.

During the database expansion phase, `supported_symbols.provider` and
`supported_symbols.provider_symbol` SHALL remain present and unchanged for compatibility with the
deployed single-provider application.

#### Scenario: Simplified normalized registry schema is migrated

- **WHEN** the database is upgraded through this change
- **THEN** `supported_symbols` retains its existing columns and constraints
- **AND** `symbol_provider_mappings` exists with a foreign key to `supported_symbols`
- **AND** each mapping contains one asset-wide `is_active` selection flag
- **AND** mappings contain no equivalence key or route-specific capability priorities
- **AND** no existing canonical symbol, provider mapping, or candle row is removed

### Requirement: Existing provider mappings are normalized without behavior change

The migration SHALL preserve every existing canonical symbol's legacy provider mapping as exactly
one active normalized mapping. The active mapping SHALL represent the provider selection shared by
quote, candle, and stream, without automatic fallback.

#### Scenario: Current catalog is upgraded

- **WHEN** the migration runs against the current fully seeded catalog
- **THEN** every `supported_symbols` row has exactly one corresponding normalized mapping
- **AND** each normalized mapping preserves the row's provider and provider symbol
- **AND** each normalized mapping is active

#### Scenario: Canonical symbol is disabled

- **WHEN** an existing `supported_symbols` row is disabled when the migration runs
- **THEN** its provider mapping is still preserved as the active normalized mapping
- **AND** the canonical symbol's enabled state remains unchanged

#### Scenario: Expansion migration completes

- **WHEN** all normalized mappings have been transformed and validated
- **THEN** quote, candle, stream, symbol-listing, and candle-persistence behavior remains unchanged
- **AND** no fallback or per-route provider selection is introduced

### Requirement: Normalized provider mapping integrity is enforced

The database MUST reject ambiguous or invalid normalized provider mappings using foreign-key,
uniqueness, check, and partial-index constraints.

#### Scenario: Provider symbol identity is duplicated

- **WHEN** two normalized rows use the same provider and provider symbol
- **THEN** persistence rejects the duplicate mapping

#### Scenario: Provider is duplicated for one canonical symbol

- **WHEN** two normalized rows use the same provider for one canonical supported symbol
- **THEN** persistence rejects the duplicate mapping

#### Scenario: Two mappings are active

- **WHEN** two mappings for one canonical symbol are marked active
- **THEN** persistence rejects the second active mapping

#### Scenario: Mapping identifier is empty

- **WHEN** a normalized mapping has an empty or whitespace-only provider or provider symbol
- **THEN** persistence rejects the mapping

#### Scenario: Canonical symbol is deleted

- **WHEN** a canonical supported-symbol row is deleted
- **THEN** its normalized provider mappings are deleted by the foreign-key cascade

### Requirement: Mapping normalization is reversibly expandable

The database migration SHALL be reversible without reconstructing legacy provider data or deleting
normalized mapping rows.

#### Scenario: Simplification migration is downgraded

- **WHEN** the database is downgraded from this change to revision `20260727_0017`
- **THEN** every normalized provider mapping row is preserved
- **AND** the removed `20260727_0017` mapping fields and constraints are reconstructed
  deterministically
- **AND** the legacy provider and provider-symbol columns remain unchanged

#### Scenario: Expansion migration is downgraded

- **WHEN** the database is downgraded from revision `20260727_0017` to revision `20260727_0016`
- **THEN** `symbol_provider_mappings` is removed
- **AND** the legacy provider and provider-symbol columns retain their pre-upgrade values
- **AND** the existing application can continue using the legacy registry schema
