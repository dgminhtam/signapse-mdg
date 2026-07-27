## MODIFIED Requirements

### Requirement: Supported symbols are persisted

The gateway SHALL store canonical supported symbols in PostgreSQL with a unique canonical symbol,
an enabled state, display and calendar metadata, and audit timestamps. The gateway SHALL also
store normalized provider mappings in `symbol_provider_mappings`, with each mapping referencing one
canonical supported symbol and defining provider identity, provider symbol, equivalence key,
enabled state, capability priorities, and audit timestamps.

During the database expansion phase, `supported_symbols.provider` and
`supported_symbols.provider_symbol` SHALL remain present and unchanged for compatibility with the
deployed single-provider application.

#### Scenario: Normalized registry schema is migrated

- **WHEN** the database is upgraded through this change
- **THEN** `supported_symbols` retains its existing columns and constraints
- **AND** `symbol_provider_mappings` exists with a foreign key to `supported_symbols`
- **AND** no existing canonical symbol, provider mapping, or candle row is removed or modified

## ADDED Requirements

### Requirement: Existing provider mappings are normalized without behavior change

The migration SHALL copy every existing canonical symbol's legacy provider mapping into exactly
one enabled normalized mapping with quote, candle, and stream priority `0`, and SHALL use a unique
opaque equivalence key that does not imply equivalence with another mapping.

#### Scenario: Current catalog is upgraded

- **WHEN** the migration runs against the current fully seeded catalog
- **THEN** every `supported_symbols` row has exactly one corresponding normalized mapping
- **AND** each normalized mapping preserves the row's provider and provider symbol
- **AND** each normalized mapping has quote, candle, and stream priority `0`
- **AND** each normalized mapping has equivalence key `mapping:<supported_symbol_id>`

#### Scenario: Canonical symbol is disabled

- **WHEN** an existing `supported_symbols` row is disabled when the migration runs
- **THEN** its provider mapping is still copied as an enabled normalized mapping
- **AND** the canonical symbol's enabled state remains unchanged

#### Scenario: Expansion migration completes

- **WHEN** all normalized mappings have been copied and validated
- **THEN** quote, candle, stream, symbol-listing, and candle-persistence behavior remains unchanged
- **AND** no secondary provider mapping is introduced

### Requirement: Normalized provider mapping integrity is enforced

The database MUST reject ambiguous, invalid, or unusable normalized provider mappings using
foreign-key, uniqueness, and check constraints.

#### Scenario: Provider symbol identity is duplicated

- **WHEN** two normalized rows use the same provider and provider symbol
- **THEN** persistence rejects the duplicate mapping

#### Scenario: Provider is duplicated for one canonical symbol

- **WHEN** two normalized rows use the same provider for one canonical supported symbol
- **THEN** persistence rejects the duplicate mapping

#### Scenario: Capability priority is ambiguous

- **WHEN** two mappings for one canonical symbol use the same non-null quote, candle, or stream
  priority
- **THEN** persistence rejects the ambiguous priority

#### Scenario: Priority is negative

- **WHEN** a normalized mapping defines a negative quote, candle, or stream priority
- **THEN** persistence rejects the mapping

#### Scenario: Mapping has no capability

- **WHEN** a normalized mapping has null quote, candle, and stream priorities
- **THEN** persistence rejects the mapping

#### Scenario: Mapping identifier is empty

- **WHEN** a normalized mapping has an empty or whitespace-only provider, provider symbol, or
  equivalence key
- **THEN** persistence rejects the mapping

#### Scenario: Canonical symbol is deleted

- **WHEN** a canonical supported-symbol row is deleted
- **THEN** its normalized provider mappings are deleted by the foreign-key cascade

### Requirement: Mapping normalization is reversibly expandable

The database migration SHALL be reversible without reconstructing legacy provider data.

#### Scenario: Expansion migration is downgraded

- **WHEN** the database is downgraded from this change to revision `20260727_0016`
- **THEN** `symbol_provider_mappings` is removed
- **AND** the legacy provider and provider-symbol columns retain their pre-upgrade values
- **AND** the existing application can continue using the legacy registry schema
