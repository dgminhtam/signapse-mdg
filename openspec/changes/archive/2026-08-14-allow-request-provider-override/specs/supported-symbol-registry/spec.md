## MODIFIED Requirements

### Requirement: Enabled symbols can be listed

The gateway SHALL expose `GET /v1/symbols` and return only enabled registry records with their Default Provider fields and every configured Provider Mapping, ordered by canonical symbol ascending.

Each symbol object SHALL retain `provider` and `providerSymbol` for the Default Provider and SHALL add `providerMappings`. Each mapping object SHALL contain exactly `provider`, `providerSymbol`, and `isDefault`; the default mapping SHALL appear first and remaining mappings SHALL be ordered by case-sensitive Provider Identifier.

#### Scenario: Required symbols are enabled

- **WHEN** a client sends `GET /v1/symbols` after the current migrations
- **THEN** the gateway responds with HTTP status `200`
- **AND** every enabled symbol retains its canonical metadata, default `provider`, default `providerSymbol`, enabled value, and price display precision
- **AND** every configured mapping for that symbol appears once in `providerMappings`
- **AND** exactly one mapping has `isDefault=true`
- **AND** the symbols are ordered by canonical symbol ascending

#### Scenario: Asset has a non-default alternative

- **WHEN** enabled `AAPL` has default mapping `TWELVE_DATA:AAPL` and non-default mapping `YFINANCE:AAPL`
- **THEN** the top-level provider fields contain `TWELVE_DATA` and `AAPL`
- **AND** `providerMappings` contains both mappings
- **AND** the Twelve Data mapping appears first with `isDefault=true`
- **AND** the YFINANCE mapping has `isDefault=false`

#### Scenario: A registry record is disabled

- **WHEN** a registry record has enabled value `false`
- **THEN** `GET /v1/symbols` omits that record and all of its mappings

#### Scenario: No symbols are enabled

- **WHEN** the registry contains no enabled records
- **THEN** `GET /v1/symbols` responds with HTTP status `200`
- **AND** the response body is `{"symbols":[]}`

#### Scenario: Provider is operationally unavailable

- **WHEN** a configured provider is temporarily unavailable
- **THEN** its verified mapping remains in `providerMappings`
- **AND** the response adds no runtime health or availability field

### Requirement: Symbol API uses the database registry

The gateway MUST obtain the supported-symbol response through the symbol repository by joining every enabled canonical record to all of its normalized Provider Mappings, MUST derive the top-level provider fields and `isDefault` from the single active mapping, MUST NOT read legacy provider columns, and MUST NOT return a hard-coded mapping or fallback registry.

#### Scenario: Active mapping is changed

- **WHEN** an enabled symbol's active normalized Provider Mapping is changed in PostgreSQL
- **THEN** a subsequent `GET /v1/symbols` response reflects the newly active provider and provider symbol in the top-level fields
- **AND** the new default mapping appears first with `isDefault=true`
- **AND** the previously active mapping remains listed with `isDefault=false` when it still exists

#### Scenario: Non-default mapping is added

- **WHEN** a verified non-default Provider Mapping is added for an enabled asset
- **THEN** a subsequent `GET /v1/symbols` response includes it in `providerMappings`
- **AND** the top-level Default Provider fields remain unchanged

### Requirement: Active provider mappings are authoritative at runtime

The gateway MUST require every enabled canonical symbol to have exactly one active Provider Mapping. That mapping SHALL remain authoritative for symbol-listing default fields, market-data requests without Provider Override, and candle backfill. A market-data request with Provider Override MAY select another configured mapping for the same asset without changing the active mapping or consulting any unconfigured mapping.

#### Scenario: Active Provider Mapping is switched

- **WHEN** a provider switch deactivates the current mapping and activates another mapping for the same canonical symbol in one transaction
- **THEN** subsequent symbol listings, default market-data requests, and backfill work use the newly active provider and provider symbol
- **AND** an in-flight Provider Selection remains unchanged

#### Scenario: Explicit non-default Provider Mapping is selected

- **WHEN** a market-data request supplies a Provider Override matching a configured non-default mapping
- **THEN** that request uses the non-default provider and provider symbol
- **AND** the active mapping remains authoritative for later requests that omit Provider Override

#### Scenario: Enabled symbol has no active mapping

- **WHEN** a repository reads an enabled canonical symbol that has no active Provider Mapping
- **THEN** the gateway fails with the sanitized `DATABASE_UNAVAILABLE` boundary
- **AND** it does not omit the symbol silently
- **AND** it does not bypass the invalid registry state through Provider Override

#### Scenario: Override mapping is absent

- **WHEN** an enabled asset has a valid active mapping but lacks the explicitly requested Provider Mapping
- **THEN** the asset fails with `UNSUPPORTED_PROVIDER`
- **AND** the gateway does not select another inactive or active mapping as fallback
