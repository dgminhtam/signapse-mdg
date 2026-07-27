# Supported Symbol Registry Specification

## Purpose

Define the PostgreSQL-backed source of truth and HTTP contract for symbols supported by the
market data gateway.
## Requirements
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
- **AND** no existing canonical symbol, provider mapping, or candle row is removed

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

### Requirement: Required MVP symbols are seeded

The database migration SHALL seed exactly the required MVP symbol mappings without requiring
application startup.

#### Scenario: Initial seed is applied

- **WHEN** the migration is applied to an empty database
- **THEN** the registry contains enabled `BTC/USD` mapped to `TWELVE_DATA:BTC/USD`
- **AND** the registry contains enabled `ETH/USD` mapped to `TWELVE_DATA:ETH/USD`

#### Scenario: Seed operation is repeated

- **WHEN** the seed operation encounters either required mapping already present
- **THEN** it updates that mapping without creating a duplicate record
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

### Requirement: Database failures have a stable response

The gateway SHALL return a stable service-unavailable error when the symbol registry cannot be
queried and SHALL NOT expose database credentials, SQL, or stack traces.

#### Scenario: Database configuration is absent

- **WHEN** a client sends `GET /v1/symbols` without a configured `DATABASE_URL`
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `DATABASE_UNAVAILABLE`

#### Scenario: PostgreSQL cannot be reached

- **WHEN** a client sends `GET /v1/symbols` and the configured database query fails
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `DATABASE_UNAVAILABLE`
- **AND** the response does not disclose internal database details

### Requirement: Health remains database-independent

The database registry capability MUST NOT require database configuration or connectivity for
the process health endpoint.

#### Scenario: Health is requested without database access

- **WHEN** the gateway is running without `DATABASE_URL` or PostgreSQL connectivity
- **THEN** `GET /health` continues to satisfy the service-health specification

### Requirement: Database settings use deployment configuration

The gateway SHALL read its database URL and pool settings from typed environment configuration,
and the repository SHALL contain only placeholder database values.

#### Scenario: Placeholder configuration is distributed

- **WHEN** a contributor inspects the repository environment example
- **THEN** it documents `DATABASE_URL` and database pool settings
- **AND** it contains no usable database credential

### Requirement: Current Forex catalog symbols are seeded

The database migration introduced by this change SHALL seed the current Forex catalog symbols as
enabled registry records mapped to the Twelve Data provider.

#### Scenario: Forex seed is applied to an upgraded database

- **WHEN** the database is upgraded through the Forex seed migration
- **THEN** the registry contains enabled `EUR/USD` with asset class `FOREX`, provider
  `TWELVE_DATA`, and provider symbol `EUR/USD`
- **AND** the registry contains enabled `GBP/USD` with asset class `FOREX`, provider
  `TWELVE_DATA`, and provider symbol `GBP/USD`
- **AND** the registry contains enabled `USD/JPY` with asset class `FOREX`, provider
  `TWELVE_DATA`, and provider symbol `USD/JPY`
- **AND** the registry contains enabled `AUD/USD` with asset class `FOREX`, provider
  `TWELVE_DATA`, and provider symbol `AUD/USD`
- **AND** the registry contains enabled `XAU/USD` with asset class `COMMODITY`, provider
  `TWELVE_DATA`, and provider symbol `XAU/USD`
- **AND** the registry contains enabled `AAPL`, `TSLA`, `NVDA`, and `MSFT` with asset class
  `US_STOCK`, provider `TWELVE_DATA`, and matching provider symbols
- **AND** existing `BTC/USD` and `ETH/USD` canonical rows remain enabled

#### Scenario: Forex seed operation is repeated

- **WHEN** the Forex seed operation encounters any required Forex mapping already present
- **THEN** it updates that mapping without creating a duplicate registry record

#### Scenario: Supported symbols are listed after Forex seed

- **WHEN** a client sends `GET /v1/symbols` after the Forex seed migration is applied
- **THEN** the response can include the enabled Forex records ordered by canonical symbol
  ascending with the existing symbol response shape
### Requirement: Forex registry seeding does not enable Forex market data APIs

Seeding Forex symbols SHALL NOT change public quote, candle, or WebSocket market-data behavior in
this change.

#### Scenario: Public data APIs are used after Forex seed

- **WHEN** the Forex registry rows exist
- **THEN** existing Binance-backed crypto quote, candle, and stream behavior remains unchanged
- **AND** no Twelve Data provider call is made by public quote, candle, or WebSocket routes until
  a later provider-routing change explicitly enables it

### Requirement: Validated WTI and ETF symbols are seeded

The database SHALL seed enabled `WTI`, `SPY`, and `QQQ` mappings through `TWELVE_DATA`.

#### Scenario: WTI and ETF seed is applied
- **WHEN** the WTI and ETF seed migration is applied
- **THEN** `WTI` is enabled as `COMMODITY` mapped to `TWELVE_DATA:WTI`
- **AND** `SPY` and `QQQ` are enabled as `ETF` with matching provider symbols

#### Scenario: WTI and ETF seed is repeated
- **WHEN** a required canonical symbol already exists
- **THEN** the migration restores its required mapping without duplication

### Requirement: ETF is a public registry asset class

The supported-symbol API SHALL expose `ETF` for enabled ETF records.

#### Scenario: Seeded ETFs are listed
- **WHEN** a client sends `GET /v1/symbols`
- **THEN** `QQQ` and `SPY` are returned with asset class `ETF`

### Requirement: yfinance planned catalog symbols are seeded

The database SHALL seed enabled mappings for the planned catalog assets that do not already have a
provider, using `YFINANCE` as the provider identifier.

#### Scenario: yfinance seed is applied

- **WHEN** the yfinance seed migration is applied
- **THEN** `XAG/USD` is enabled as `COMMODITY` mapped to `YFINANCE:SI=F`
- **AND** `BRENT` is enabled as `COMMODITY` mapped to `YFINANCE:BZ=F`
- **AND** `NATGAS` is enabled as `COMMODITY` mapped to `YFINANCE:NG=F`
- **AND** `COFFEE` is enabled as `COMMODITY` mapped to `YFINANCE:KC=F`
- **AND** `SUGAR` is enabled as `COMMODITY` mapped to `YFINANCE:SB=F`
- **AND** `WHEAT` is enabled as `COMMODITY` mapped to `YFINANCE:ZW=F`
- **AND** `CORN` is enabled as `COMMODITY` mapped to `YFINANCE:ZC=F`
- **AND** `SPX` is enabled as `STOCK_INDEX` mapped to `YFINANCE:^GSPC`
- **AND** `NDX` is enabled as `STOCK_INDEX` mapped to `YFINANCE:^NDX`
- **AND** `DJI` is enabled as `STOCK_INDEX` mapped to `YFINANCE:^DJI`

#### Scenario: yfinance seed is repeated

- **WHEN** any required yfinance canonical symbol already exists
- **THEN** the migration restores its required asset class, provider, provider symbol, and enabled
  value without creating duplicate registry records

#### Scenario: Existing provider mappings are preserved

- **WHEN** the yfinance seed migration is applied
- **THEN** existing `BINANCE_SPOT` and `TWELVE_DATA` registry mappings remain enabled and unchanged

### Requirement: STOCK_INDEX is a public registry asset class

The supported-symbol API SHALL expose `STOCK_INDEX` for enabled stock-index registry records.

#### Scenario: Seeded stock indexes are listed

- **WHEN** a client sends `GET /v1/symbols` after the yfinance seed migration is applied
- **THEN** `SPX`, `NDX`, and `DJI` can be returned with asset class `STOCK_INDEX`
- **AND** the response uses the existing supported-symbol response shape

### Requirement: yfinance registry seeding does not enable market-data APIs

Seeding yfinance symbols SHALL NOT change public quote, candle, or WebSocket market-data routing in
this change.

#### Scenario: Market-data request targets a yfinance-seeded symbol

- **WHEN** a client requests quote, candle, or stream data for an enabled `YFINANCE` symbol
- **THEN** the gateway makes no yfinance upstream request
- **AND** no yfinance adapter is required to serve the request in this change

### Requirement: Supported symbols can reference market calendars

The supported-symbol registry SHALL allow each symbol to store nullable inline market-calendar
configuration when a verified mapping exists.

#### Scenario: Registry calendar config columns are migrated

- **WHEN** the database is upgraded through this change
- **THEN** `supported_symbols` has nullable `calendar_source`, `calendar_name`, and
  `calendar_timezone` columns
- **AND** `supported_symbols` does not require `calendar_code` to reference a separate calendar
  table

#### Scenario: Obvious calendar config is seeded

- **WHEN** the migration runs against a database containing current supported symbol rows
- **THEN** Forex pairs and spot `XAU/USD` can store `pandas_market_calendars`, `FOREX`, and
  `America/New_York`
- **AND** US stocks, ETFs, and stock indexes can store `pandas_market_calendars`, `NYSE`, and
  `America/New_York`
- **AND** crypto symbols can store `internal`, `24/7`, and `UTC`
- **AND** verified futures proxy symbols can store their mapped `pandas_market_calendars` calendar
  names and time zones

#### Scenario: Public symbol response remains unchanged

- **WHEN** a client sends `GET /v1/symbols` after this migration
- **THEN** the response uses the existing supported-symbol response shape
- **AND** it does not expose `calendar_source`, `calendar_name`, or `calendar_timezone`

### Requirement: Supported symbols define price display decimals

The gateway SHALL persist `price_display_decimals` for every supported symbol as an integer from
0 through 18 inclusive, SHALL require an explicit value, and SHALL use it only when serializing
public price fields without constraining provider-normalized, cached, aggregated, or persisted
market-data precision.

#### Scenario: Display precision schema is migrated

- **WHEN** the database is upgraded through this change
- **THEN** `supported_symbols` contains a non-null `price_display_decimals` column
- **AND** the database rejects values below 0 or above 18
- **AND** the column has no default that silently assigns precision to a future symbol

#### Scenario: Existing catalog is backfilled

- **WHEN** the display precision migration is applied to the current supported-symbol catalog
- **THEN** `AUD/USD`, `EUR/USD`, and `GBP/USD` have value `5`
- **AND** `USD/JPY`, `XAG/USD`, and `NATGAS` have value `3`
- **AND** `BTC/USD`, `ETH/USD`, `XAU/USD`, `WTI`, `BRENT`, `COFFEE`, `SUGAR`, `WHEAT`,
  `CORN`, `AAPL`, `TSLA`, `NVDA`, `MSFT`, `SPY`, `QQQ`, `SPX`, `NDX`, and `DJI` have value `2`

#### Scenario: Future symbol omits display precision

- **WHEN** a new supported-symbol record is inserted without `price_display_decimals`
- **THEN** persistence rejects the record

#### Scenario: Market value is held internally

- **WHEN** a provider-normalized price has more fractional digits than its symbol display precision
- **THEN** domain values, caches, candle aggregation, and persistence retain the normalized value
- **AND** display rounding occurs only when a public price field is serialized

### Requirement: Symbol API exposes price display decimals

The gateway SHALL expose each enabled symbol's persisted display precision as the integer
`priceDisplayDecimals` in `GET /v1/symbols`.

#### Scenario: Enabled symbol is listed

- **WHEN** a client sends `GET /v1/symbols`
- **THEN** every returned symbol contains `priceDisplayDecimals`
- **AND** the value matches that symbol's persisted `price_display_decimals`

#### Scenario: XAU display metadata is listed

- **WHEN** enabled `XAU/USD` has persisted `price_display_decimals` value `2`
- **AND** a client sends `GET /v1/symbols`
- **THEN** the `XAU/USD` object contains `"priceDisplayDecimals":2`

#### Scenario: Registry display precision changes

- **WHEN** an enabled symbol's persisted `price_display_decimals` value changes
- **THEN** a subsequent `GET /v1/symbols` response reflects the changed value

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
