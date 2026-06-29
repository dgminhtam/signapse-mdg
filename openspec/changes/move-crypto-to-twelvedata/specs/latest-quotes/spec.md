## MODIFIED Requirements

### Requirement: Quote requests use enabled registry mappings

The gateway MUST validate canonical symbols and obtain provider mappings from enabled PostgreSQL
registry records and MUST NOT use a hard-coded runtime mapping.

#### Scenario: Enabled crypto symbols are requested

- **WHEN** a client requests `BTC/USD,ETH/USD` and both registry records are enabled
- **THEN** the gateway maps them to persisted provider symbols `BTC/USD` and `ETH/USD`
- **AND** it uses their persisted `TWELVE_DATA` provider mapping for refreshes that need provider
  data

#### Scenario: Enabled Forex symbols are requested

- **WHEN** a client requests `EUR/USD,GBP/USD,USD/JPY,AUD/USD,XAU/USD,AAPL,TSLA,NVDA,MSFT` and
  those registry records are enabled
- **THEN** the gateway maps them to persisted provider symbols `EUR/USD`, `GBP/USD`, `USD/JPY`,
  `AUD/USD`, `XAU/USD`, `AAPL`, `TSLA`, `NVDA`, and `MSFT`
- **AND** it uses their persisted `TWELVE_DATA` provider mapping for refreshes that need provider
  data

#### Scenario: Unknown or disabled symbol is requested

- **WHEN** a well-formed request contains a canonical symbol that has no enabled registry record
- **THEN** the response includes an `UNSUPPORTED_SYMBOL` error for that symbol
- **AND** other requested symbols continue to be processed

#### Scenario: Persisted provider mapping changes

- **WHEN** an enabled symbol's provider mapping is changed in PostgreSQL
- **THEN** a subsequent quote request uses the changed persisted mapping

#### Scenario: Registry is unavailable

- **WHEN** the gateway cannot query the symbol registry for a quote request
- **THEN** it responds with HTTP status `503`
- **AND** the request-level error code is `DATABASE_UNAVAILABLE`
- **AND** no provider quote request is made

### Requirement: Binance latest prices are fetched in a batch

The gateway SHALL fetch uncached Binance Spot prices through one Binance ticker-price operation
per quote refresh containing all required Binance provider symbols in that refresh group.

#### Scenario: Binance-backed quotes need refresh

- **WHEN** one or more enabled symbols mapped to `BINANCE_SPOT` have no reusable cache entries
- **THEN** the adapter requests those provider symbols in one Binance ticker-price batch

#### Scenario: Only one Binance-backed quote needs refresh

- **WHEN** one requested Binance-backed quote is reusable from cache and another is not
- **THEN** the Binance batch contains only the provider symbol requiring refresh

#### Scenario: Concurrent requests need the same refresh

- **WHEN** concurrent requests require refresh for the same symbol
- **THEN** the gateway coalesces the refresh work
- **AND** does not issue duplicate simultaneous provider calls for that symbol

### Requirement: Quote refreshes are isolated by provider group

The gateway SHALL group uncached quote refreshes by each enabled symbol's persisted provider and
SHALL isolate provider failures to symbols refreshed through the failing provider group.

#### Scenario: Mixed Twelve Data catalog symbols are requested

- **WHEN** a client requests enabled `BTC/USD`, `ETH/USD`, `EUR/USD`, and `GBP/USD` in one quote
  request
- **THEN** the gateway refreshes all four provider symbols through the Twelve Data adapter
- **AND** the final `quotes` and `errors` arrays preserve the first occurrence order from the
  request

#### Scenario: One provider group fails

- **WHEN** a mixed quote request includes Binance-backed and Twelve Data-backed symbols
- **AND** the Twelve Data refresh fails while the Binance refresh succeeds
- **THEN** successful Binance-backed symbols appear in `quotes`
- **AND** affected Twelve Data-backed symbols appear in `errors` with `PROVIDER_UNAVAILABLE`
- **AND** the response status remains `200`
