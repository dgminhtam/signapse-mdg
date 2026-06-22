## ADDED Requirements

### Requirement: Forex latest quotes are available through the existing quote endpoint

The gateway SHALL allow enabled seeded Forex symbols mapped to `TWELVE_DATA` to be requested
through `GET /v1/quotes` using the existing quote request and response contract.

#### Scenario: Forex symbols are requested

- **WHEN** a client requests enabled `EUR/USD`, `GBP/USD`, `USD/JPY`, or `AUD/USD` through
  `GET /v1/quotes`
- **THEN** the gateway requests latest prices from the Twelve Data Forex provider for those
  provider symbols
- **AND** each successful public quote contains exactly `symbol`, `price`, and `receivedAt`
- **AND** `price` is serialized as a decimal string
- **AND** provider identity, provider symbol, asset class, volume, provider time, and freshness
  state are not exposed in the public quote

#### Scenario: Twelve Data is not configured

- **WHEN** an enabled Forex quote requires Twelve Data but Twelve Data configuration is missing
  or unusable
- **THEN** the affected Forex symbol receives a `PROVIDER_UNAVAILABLE` error when no fresh cached
  quote can be used
- **AND** Binance-backed crypto quote requests in the same deployment can still succeed

### Requirement: Quote refreshes are isolated by provider group

The gateway SHALL group uncached quote refreshes by each enabled symbol's persisted provider and
SHALL isolate provider failures to symbols refreshed through the failing provider group.

#### Scenario: Mixed crypto and Forex symbols are requested

- **WHEN** a client requests enabled `BTC/USD`, `ETH/USD`, `EUR/USD`, and `GBP/USD` in one quote
  request
- **THEN** the gateway refreshes Binance provider symbols through the Binance quote adapter
- **AND** the gateway refreshes Twelve Data provider symbols through the Twelve Data Forex adapter
- **AND** the final `quotes` and `errors` arrays preserve the first occurrence order from the
  request

#### Scenario: One provider group fails

- **WHEN** a mixed quote request includes Binance-backed and Twelve Data-backed symbols
- **AND** the Twelve Data refresh fails while the Binance refresh succeeds
- **THEN** successful Binance-backed symbols appear in `quotes`
- **AND** affected Twelve Data-backed symbols appear in `errors` with `PROVIDER_UNAVAILABLE`
- **AND** the response status remains `200`

## MODIFIED Requirements

### Requirement: Quote requests use enabled registry mappings

The gateway MUST validate canonical symbols and obtain provider mappings from enabled PostgreSQL
registry records and MUST NOT use a hard-coded runtime mapping.

#### Scenario: Enabled crypto symbols are requested

- **WHEN** a client requests `BTC/USD,ETH/USD` and both registry records are enabled
- **THEN** the gateway maps them to persisted provider symbols `BTCUSD` and `ETHUSD`
- **AND** it uses their persisted `BINANCE_SPOT` provider mapping for refreshes that need provider
  data

#### Scenario: Enabled Forex symbols are requested

- **WHEN** a client requests `EUR/USD,GBP/USD,USD/JPY,AUD/USD` and those registry records are
  enabled
- **THEN** the gateway maps them to persisted provider symbols `EUR/USD`, `GBP/USD`, `USD/JPY`,
  and `AUD/USD`
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

#### Scenario: Both required crypto quotes need refresh

- **WHEN** enabled `BTC/USD` and `ETH/USD` have no reusable cache entries
- **THEN** the adapter requests `BTCUSD` and `ETHUSD` in one Binance ticker-price batch

#### Scenario: Only one crypto quote needs refresh

- **WHEN** one requested Binance-backed quote is reusable from cache and another is not
- **THEN** the Binance batch contains only the provider symbol requiring refresh

#### Scenario: Concurrent requests need the same refresh

- **WHEN** concurrent requests require refresh for the same symbol
- **THEN** the gateway coalesces the refresh work
- **AND** does not issue duplicate simultaneous provider calls for that symbol

### Requirement: Provider prices are normalized without floating point

The gateway SHALL validate provider prices as finite positive decimal values and SHALL expose a
minimal provider-agnostic public quote without leaking provider payload or routing metadata.

#### Scenario: Valid provider prices are returned

- **WHEN** Binance or Twelve Data returns valid prices for requested provider symbols
- **THEN** each public quote contains exactly `symbol`, `price`, and `receivedAt`
- **AND** `symbol` is the canonical gateway symbol
- **AND** `price` is serialized as a decimal string
- **AND** `receivedAt` is a UTC gateway timestamp
- **AND** provider identity, provider symbol, asset class, volume, provider time, and freshness
  state are not exposed in the public quote

#### Scenario: One provider price is invalid or missing

- **WHEN** a provider response has a valid price for one requested provider symbol but omits or
  returns an invalid price for another
- **THEN** the valid symbol is returned in `quotes` using the minimal public representation
- **AND** the affected symbol receives a `PROVIDER_UNAVAILABLE` error

### Requirement: Quote cache limits provider requests

The gateway SHALL store latest normalized quotes in a process-local cache using configurable TTL
and freshness thresholds while keeping cache and freshness metadata internal.

#### Scenario: Cache entry is within TTL

- **WHEN** a requested quote's age does not exceed `QUOTE_CACHE_TTL_SECONDS`
- **THEN** the cached quote is returned using the minimal public representation
- **AND** no provider request is made for that symbol

#### Scenario: Cache entry has exceeded TTL

- **WHEN** a requested quote is older than `QUOTE_CACHE_TTL_SECONDS`
- **THEN** the gateway attempts to refresh that symbol from its persisted provider mapping

#### Scenario: Refresh fails but cached quote is still fresh

- **WHEN** provider refresh fails and the cached quote's age does not exceed
  `QUOTE_STALE_AFTER_SECONDS`
- **THEN** the cached quote is returned using the minimal public representation
- **AND** no public freshness field is added to the quote

#### Scenario: Refresh fails and cached quote is stale

- **WHEN** provider refresh fails and the cached quote's age exceeds `QUOTE_STALE_AFTER_SECONDS`
- **THEN** the response contains a `DATA_STALE` error for that symbol
- **AND** the stale quote is not returned in `quotes`

### Requirement: Provider failures are isolated and sanitized

The gateway SHALL convert provider SDK, timeout, rate-limit, transport, configuration, and
invalid-response failures into stable per-symbol errors without exposing internal URLs, payloads,
credentials, or stack traces.

#### Scenario: Provider request fails with no cached quote

- **WHEN** a provider refresh fails and a requested symbol in that provider group has no cached
  quote
- **THEN** that symbol receives a `PROVIDER_UNAVAILABLE` error
- **AND** the error contains no internal exception detail

#### Scenario: Provider group failure affects multiple uncached symbols

- **WHEN** one failed provider refresh group contains multiple uncached provider symbols
- **THEN** each affected canonical symbol receives its own `PROVIDER_UNAVAILABLE` error
- **AND** symbols from successful provider groups can still be returned in `quotes`

### Requirement: Quote settings use typed deployment configuration

The gateway SHALL use typed settings for provider base URLs, provider timeout, quote cache TTL,
stale threshold, maximum quote symbols, and Twelve Data credentials, with non-secret defaults and
secret placeholders documented in the environment example.

#### Scenario: Default quote configuration is used

- **WHEN** quote-specific environment variables are absent
- **THEN** the gateway uses the documented non-secret defaults

#### Scenario: Invalid quote configuration is supplied

- **WHEN** TTL, stale threshold, timeout, or request-size settings violate their numeric
  constraints
- **THEN** application configuration validation fails explicitly

#### Scenario: Twelve Data API key is absent

- **WHEN** `TWELVEDATA_API_KEY` is not configured
- **THEN** application startup does not fail solely because of the missing Twelve Data credential
- **AND** Forex quote refreshes that require Twelve Data are reported through symbol-level
  provider failure behavior
