## MODIFIED Requirements

### Requirement: Supported symbols are persisted

The gateway SHALL store canonical supported symbols in PostgreSQL with a unique canonical symbol,
an enabled state, display and calendar metadata, and audit timestamps. The gateway SHALL store all
provider identities exclusively in `symbol_provider_mappings`, with each mapping referencing one
canonical supported symbol and defining provider identity, provider symbol, active-selection state,
and audit timestamps.

#### Scenario: Contracted normalized registry schema is migrated

- **WHEN** the database is upgraded through this change
- **THEN** `supported_symbols` contains no `provider` or `provider_symbol` column
- **AND** `supported_symbols` contains no legacy provider-symbol uniqueness constraint
- **AND** `symbol_provider_mappings` remains linked to `supported_symbols`
- **AND** no canonical symbol, normalized provider mapping, or candle row is removed

### Requirement: Enabled symbols can be listed

The gateway SHALL expose `GET /v1/symbols` and return only enabled registry records joined to their
single active normalized provider mapping, ordered by canonical symbol ascending.

#### Scenario: Required symbols are enabled

- **WHEN** a client sends `GET /v1/symbols` after the initial migration
- **THEN** the gateway responds with HTTP status `200`
- **AND** the response contains `BTC/USD` with asset class `CRYPTO`, provider `TWELVE_DATA`,
  provider symbol `BTC/USD`, and enabled value `true`
- **AND** the response contains `ETH/USD` with asset class `CRYPTO`, provider `TWELVE_DATA`,
  provider symbol `ETH/USD`, and enabled value `true`
- **AND** the provider fields come from each symbol's active normalized mapping
- **AND** the symbols are ordered by canonical symbol ascending

#### Scenario: A registry record is disabled

- **WHEN** a registry record has enabled value `false`
- **THEN** `GET /v1/symbols` omits that record

#### Scenario: No symbols are enabled

- **WHEN** the registry contains no enabled records
- **THEN** `GET /v1/symbols` responds with HTTP status `200`
- **AND** the response body is `{"symbols":[]}`

### Requirement: Symbol API uses the database registry

The gateway MUST obtain the supported-symbol response through the symbol repository by joining each
enabled canonical record to its active normalized mapping, MUST NOT read legacy provider columns,
and MUST NOT return a hard-coded fallback registry.

#### Scenario: Active mapping is changed

- **WHEN** an enabled symbol's active normalized provider mapping is changed in PostgreSQL
- **THEN** a subsequent `GET /v1/symbols` response reflects the newly active provider and provider
  symbol
- **AND** no inactive mapping is returned

### Requirement: Approved provider mappings are seeded for the 24-asset catalog

The database SHALL seed the approved 24 canonical assets with one active default provider mapping
per asset and SHALL seed only the five approved inactive yfinance alternatives. The seed SHALL
contain no provider fallback, route-specific selection, priority, or gold-futures proxy.

#### Scenario: Twelve Data defaults are seeded

- **WHEN** the provider-mapping seed is applied
- **THEN** `AAPL`, `BTC/USD`, `EUR/USD`, `QQQ`, and `XAU/USD` have active `TWELVE_DATA` mappings
  using provider symbols `AAPL`, `BTC/USD`, `EUR/USD`, `QQQ`, and `XAU/USD` respectively

#### Scenario: Binance default is seeded

- **WHEN** the provider-mapping seed is applied
- **THEN** `ETH/USD` has active mapping `BINANCE_SPOT:ETHUSD`

#### Scenario: yfinance defaults are seeded

- **WHEN** the provider-mapping seed is applied
- **THEN** the active yfinance mappings are `AUD/USD:AUDUSD=X`, `BRENT:BZ=F`, `COFFEE:KC=F`,
  `CORN:ZC=F`, `DJI:^DJI`, `GBP/USD:GBPUSD=X`, `MSFT:MSFT`, `NATGAS:NG=F`, `NDX:^NDX`,
  `NVDA:NVDA`, `SPX:^GSPC`, `SPY:SPY`, `SUGAR:SB=F`, `TSLA:TSLA`, `USD/JPY:JPY=X`,
  `WHEAT:ZW=F`, `WTI:CL=F`, and `XAG/USD:SI=F`

#### Scenario: Approved alternatives are seeded

- **WHEN** the provider-mapping seed is applied
- **THEN** inactive mappings exist for `AAPL:YFINANCE:AAPL`, `BTC/USD:YFINANCE:BTC-USD`,
  `ETH/USD:YFINANCE:ETH-USD`, `EUR/USD:YFINANCE:EURUSD=X`, and
  `QQQ:YFINANCE:QQQ`
- **AND** no other inactive mapping is introduced by this seed

#### Scenario: XAU has no yfinance proxy

- **WHEN** mappings for `XAU/USD` are inspected
- **THEN** `TWELVE_DATA:XAU/USD` is its only seeded mapping
- **AND** neither `GC=F` nor another yfinance provider symbol is seeded for `XAU/USD`

#### Scenario: Fresh catalog is seeded

- **WHEN** the migration is applied to the current 24-asset catalog without custom mappings
- **THEN** `symbol_provider_mappings` contains 29 seeded mappings
- **AND** exactly 24 mappings are active
- **AND** every canonical asset has exactly one active mapping

#### Scenario: Runtime resolves approved active defaults

- **WHEN** runtime repositories list or resolve the seeded canonical symbols
- **THEN** each symbol's provider and provider symbol come from its active normalized mapping
- **AND** quote, candle, and stream requests share that provider selection

#### Scenario: Existing custom mapping is present

- **WHEN** the migration encounters a mapping not owned by the known historical seed or this seed
- **THEN** it preserves that mapping row
- **AND** the approved default remains the asset's only active mapping

#### Scenario: Seed operation is repeated

- **WHEN** the seed reconciliation is applied more than once
- **THEN** it produces the same approved mappings and active selections without duplicates

## ADDED Requirements

### Requirement: Active provider mappings are authoritative at runtime

The gateway MUST resolve every enabled canonical symbol through exactly one active
`symbol_provider_mappings` row and MUST use that resolved provider selection for symbol listing,
quotes, candles, WebSocket streams, and candle backfill without consulting inactive mappings.

#### Scenario: Active provider mapping is switched

- **WHEN** a provider switch deactivates the current mapping and activates another mapping for the
  same canonical symbol in one transaction
- **THEN** subsequent runtime reads use the newly active provider and provider symbol
- **AND** no route continues using the previously active mapping

#### Scenario: Enabled symbol has no active mapping

- **WHEN** a repository reads an enabled canonical symbol that has no active provider mapping
- **THEN** the gateway fails with the sanitized `DATABASE_UNAVAILABLE` boundary
- **AND** it does not omit the symbol silently
- **AND** it does not select an inactive mapping

### Requirement: Legacy provider storage is removed reversibly

The contract migration MUST validate normalized selections before removing
`supported_symbols.provider` and `supported_symbols.provider_symbol`, and its downgrade MUST
reconstruct a complete legacy mapping from each canonical symbol's active normalized mapping.

#### Scenario: Contract migration is upgraded

- **WHEN** every canonical symbol has exactly one active normalized mapping
- **THEN** the migration removes the legacy uniqueness constraint and provider columns
- **AND** normalized mappings and historical candle rows remain unchanged

#### Scenario: Contract migration encounters an incomplete selection

- **WHEN** any canonical symbol has no active normalized mapping before contraction
- **THEN** the migration aborts before removing legacy storage

#### Scenario: Contract migration is downgraded

- **WHEN** the database is downgraded to the previous revision
- **THEN** the migration recreates non-null `provider` and `provider_symbol` columns
- **AND** it fills them from each canonical symbol's active mapping
- **AND** it recreates the legacy provider-symbol uniqueness constraint
- **AND** it preserves all normalized mappings and candle rows

## REMOVED Requirements

### Requirement: Existing provider mappings are normalized without behavior change

**Reason**: The expansion is complete and runtime behavior now intentionally reads the normalized
active mapping instead of the legacy mirror.

**Migration**: Existing rows remain in `symbol_provider_mappings`; deploy the active-mapping runtime
before applying the contract migration.

### Requirement: Mapping normalization is reversibly expandable

**Reason**: The expansion-only rollback contract is superseded by the new reversible schema
contraction.

**Migration**: Downgrade the new contract revision to reconstruct legacy columns from active
mappings before deploying a legacy runtime.
