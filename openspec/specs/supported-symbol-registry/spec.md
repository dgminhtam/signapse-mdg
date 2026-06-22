# Supported Symbol Registry Specification

## Purpose

Define the PostgreSQL-backed source of truth and HTTP contract for symbols supported by the
market data gateway.

## Requirements

### Requirement: Supported symbols are persisted

The gateway SHALL store supported symbol mappings in PostgreSQL with a unique canonical symbol,
a unique provider and provider-symbol pair, an enabled state, and audit timestamps.

#### Scenario: Registry schema is migrated

- **WHEN** the database is upgraded to the revision introduced by this capability
- **THEN** the `supported_symbols` table exists with the required fields and uniqueness
  constraints

### Requirement: Required MVP symbols are seeded

The database migration SHALL seed exactly the required MVP symbol mappings without requiring
application startup.

#### Scenario: Initial seed is applied

- **WHEN** the migration is applied to an empty database
- **THEN** the registry contains enabled `BTC/USD` mapped to `BINANCE_SPOT:BTCUSD`
- **AND** the registry contains enabled `ETH/USD` mapped to `BINANCE_SPOT:ETHUSD`

#### Scenario: Seed operation is repeated

- **WHEN** the seed operation encounters either required mapping already present
- **THEN** it updates that mapping without creating a duplicate record

### Requirement: Enabled symbols can be listed

The gateway SHALL expose `GET /v1/symbols` and return only enabled registry records ordered by
canonical symbol ascending.

#### Scenario: Required symbols are enabled

- **WHEN** a client sends `GET /v1/symbols` after the initial migration
- **THEN** the gateway responds with HTTP status `200`
- **AND** the response contains `BTC/USD` with asset class `CRYPTO`, provider `BINANCE_SPOT`,
  provider symbol `BTCUSD`, and enabled value `true`
- **AND** the response contains `ETH/USD` with asset class `CRYPTO`, provider `BINANCE_SPOT`,
  provider symbol `ETHUSD`, and enabled value `true`
- **AND** the symbols are ordered by canonical symbol ascending

#### Scenario: A registry record is disabled

- **WHEN** a registry record has enabled value `false`
- **THEN** `GET /v1/symbols` omits that record

#### Scenario: No symbols are enabled

- **WHEN** the registry contains no enabled records
- **THEN** `GET /v1/symbols` responds with HTTP status `200`
- **AND** the response body is `{"symbols":[]}`

### Requirement: Symbol API uses the database registry

The gateway MUST obtain the supported-symbol response through the symbol repository and service
boundaries and MUST NOT return a hard-coded fallback registry.

#### Scenario: Persisted mapping is changed

- **WHEN** an enabled registry mapping is changed in PostgreSQL
- **THEN** a subsequent `GET /v1/symbols` response reflects the persisted mapping

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
- **AND** existing `BTC/USD` and `ETH/USD` crypto mappings remain enabled and unchanged

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
