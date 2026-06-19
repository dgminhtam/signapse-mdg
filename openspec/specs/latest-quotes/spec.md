# Latest Quotes Specification

## Purpose

Define the HTTP contract, registry lookup, provider refresh, cache, and error behavior for latest
quote requests.

## Requirements

### Requirement: Latest quotes endpoint validates request shape

The gateway SHALL expose `GET /v1/quotes` with a required comma-separated `symbols` query
parameter and SHALL enforce the configured maximum number of distinct symbols.

#### Scenario: Symbols parameter is missing

- **WHEN** a client sends `GET /v1/quotes` without `symbols`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the request-level error code is `INVALID_SYMBOLS`

#### Scenario: Symbols parameter contains no symbol

- **WHEN** `symbols` is empty or contains only commas and whitespace
- **THEN** the gateway responds with HTTP status `400`
- **AND** the request-level error code is `INVALID_SYMBOLS`

#### Scenario: Too many symbols are requested

- **WHEN** the number of distinct parsed symbols exceeds `MAX_QUOTE_SYMBOLS`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the request-level error code is `TOO_MANY_SYMBOLS`

#### Scenario: Duplicate symbols are requested

- **WHEN** a well-formed request repeats a canonical symbol
- **THEN** the gateway processes that symbol once
- **AND** preserves the first occurrence order

### Requirement: Quote requests use enabled registry mappings

The gateway MUST validate canonical symbols and obtain provider mappings from enabled PostgreSQL
registry records and MUST NOT use a hard-coded runtime mapping.

#### Scenario: Enabled required symbols are requested

- **WHEN** a client requests `BTC/USD,ETH/USD` and both registry records are enabled
- **THEN** the gateway maps them to persisted provider symbols `BTCUSD` and `ETHUSD`

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
- **AND** no Binance request is made

### Requirement: Binance latest prices are fetched in a batch

The gateway SHALL fetch uncached Binance Spot prices through one Binance ticker-price operation
containing all required provider symbols.

#### Scenario: Both required quotes need refresh

- **WHEN** enabled `BTC/USD` and `ETH/USD` have no reusable cache entries
- **THEN** the adapter requests `BTCUSD` and `ETHUSD` in one Binance ticker-price batch

#### Scenario: Only one quote needs refresh

- **WHEN** one requested quote is reusable from cache and another is not
- **THEN** the Binance batch contains only the provider symbol requiring refresh

#### Scenario: Concurrent requests need the same refresh

- **WHEN** concurrent requests require refresh for the same symbol
- **THEN** the gateway coalesces the refresh work
- **AND** does not issue duplicate simultaneous Binance calls for that symbol

### Requirement: Provider prices are normalized without floating point

The gateway SHALL validate Binance prices as finite positive decimal values and SHALL expose
normalized quote fields without leaking provider payload structure.

#### Scenario: Valid Binance prices are returned

- **WHEN** Binance returns valid prices for requested provider symbols
- **THEN** each quote contains its canonical symbol, asset class, provider, and provider symbol
- **AND** `price` is serialized as a decimal string
- **AND** `volume` is `null`
- **AND** `providerTime` is `null`
- **AND** `receivedAt` is a UTC gateway timestamp
- **AND** `stale` is `false`

#### Scenario: One provider price is invalid or missing

- **WHEN** a Binance batch response has a valid price for one requested provider symbol but omits
  or returns an invalid price for another
- **THEN** the valid symbol is returned in `quotes`
- **AND** the affected symbol receives a `PROVIDER_UNAVAILABLE` error

### Requirement: Quote cache limits provider requests

The gateway SHALL store latest normalized quotes in a process-local cache using configurable TTL
and freshness thresholds.

#### Scenario: Cache entry is within TTL

- **WHEN** a requested quote's age does not exceed `QUOTE_CACHE_TTL_SECONDS`
- **THEN** the cached quote is returned
- **AND** no Binance request is made for that symbol

#### Scenario: Cache entry has exceeded TTL

- **WHEN** a requested quote is older than `QUOTE_CACHE_TTL_SECONDS`
- **THEN** the gateway attempts to refresh that symbol from Binance

#### Scenario: Refresh fails but cached quote is still fresh

- **WHEN** Binance refresh fails and the cached quote's age does not exceed
  `QUOTE_STALE_AFTER_SECONDS`
- **THEN** the cached quote is returned with `stale` equal to `false`

#### Scenario: Refresh fails and cached quote is stale

- **WHEN** Binance refresh fails and the cached quote's age exceeds `QUOTE_STALE_AFTER_SECONDS`
- **THEN** the response contains a `DATA_STALE` error for that symbol
- **AND** the stale quote is not returned in `quotes`

### Requirement: Well-formed requests support partial outcomes

The gateway SHALL respond to a well-formed quote request with HTTP status `200` and separate
ordered `quotes` and `errors` arrays, even when one or all symbols have symbol-level failures.

#### Scenario: All symbols succeed

- **WHEN** every requested symbol has a usable quote
- **THEN** `quotes` contains each distinct symbol in request order
- **AND** `errors` is empty

#### Scenario: Some symbols fail

- **WHEN** at least one requested symbol succeeds and at least one has a symbol-level failure
- **THEN** successful symbols appear in `quotes`
- **AND** failed symbols appear in `errors`
- **AND** the response status is `200`

#### Scenario: All symbols have symbol-level failures

- **WHEN** no requested symbol has a usable quote but the request and registry lookup are valid
- **THEN** `quotes` is empty
- **AND** every failed symbol appears in `errors`
- **AND** the response status is `200`

### Requirement: Provider failures are isolated and sanitized

The gateway SHALL convert Binance SDK, timeout, rate-limit, transport, and invalid-response
failures into stable per-symbol errors without exposing internal URLs, payloads, or stack traces.

#### Scenario: Binance request fails with no cached quote

- **WHEN** the Binance batch request fails and a requested symbol has no cached quote
- **THEN** that symbol receives a `PROVIDER_UNAVAILABLE` error
- **AND** the error contains no internal exception detail

#### Scenario: Binance batch failure affects multiple uncached symbols

- **WHEN** one failed Binance batch contains multiple uncached provider symbols
- **THEN** each affected canonical symbol receives its own `PROVIDER_UNAVAILABLE` error

### Requirement: Quote settings use typed deployment configuration

The gateway SHALL use typed settings for the Binance REST base URL, provider timeout, quote cache
TTL, stale threshold, and maximum quote symbols, with non-secret defaults documented in the
environment example.

#### Scenario: Default quote configuration is used

- **WHEN** quote-specific environment variables are absent
- **THEN** the gateway uses the documented defaults

#### Scenario: Invalid quote configuration is supplied

- **WHEN** TTL, stale threshold, timeout, or request-size settings violate their numeric
  constraints
- **THEN** application configuration validation fails explicitly
