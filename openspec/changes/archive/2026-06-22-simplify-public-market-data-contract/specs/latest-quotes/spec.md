## MODIFIED Requirements

### Requirement: Provider prices are normalized without floating point

The gateway SHALL validate Binance prices as finite positive decimal values and SHALL expose a
minimal provider-agnostic public quote without leaking provider payload or routing metadata.

#### Scenario: Valid Binance prices are returned

- **WHEN** Binance returns valid prices for requested provider symbols
- **THEN** each public quote contains exactly `symbol`, `price`, and `receivedAt`
- **AND** `symbol` is the canonical gateway symbol
- **AND** `price` is serialized as a decimal string
- **AND** `receivedAt` is a UTC gateway timestamp
- **AND** provider identity, provider symbol, asset class, volume, provider time, and freshness
  state are not exposed in the public quote

#### Scenario: One provider price is invalid or missing

- **WHEN** a Binance batch response has a valid price for one requested provider symbol but omits
  or returns an invalid price for another
- **THEN** the valid symbol is returned in `quotes` using the minimal public representation
- **AND** the affected symbol receives a `PROVIDER_UNAVAILABLE` error

### Requirement: Quote cache limits provider requests

The gateway SHALL store latest normalized quotes in a process-local cache using configurable TTL
and freshness thresholds while keeping cache and freshness metadata internal.

#### Scenario: Cache entry is within TTL

- **WHEN** a requested quote's age does not exceed `QUOTE_CACHE_TTL_SECONDS`
- **THEN** the cached quote is returned using the minimal public representation
- **AND** no Binance request is made for that symbol

#### Scenario: Cache entry has exceeded TTL

- **WHEN** a requested quote is older than `QUOTE_CACHE_TTL_SECONDS`
- **THEN** the gateway attempts to refresh that symbol from Binance

#### Scenario: Refresh fails but cached quote is still fresh

- **WHEN** Binance refresh fails and the cached quote's age does not exceed
  `QUOTE_STALE_AFTER_SECONDS`
- **THEN** the cached quote is returned using the minimal public representation
- **AND** no public freshness field is added to the quote

#### Scenario: Refresh fails and cached quote is stale

- **WHEN** Binance refresh fails and the cached quote's age exceeds `QUOTE_STALE_AFTER_SECONDS`
- **THEN** the response contains a `DATA_STALE` error for that symbol
- **AND** the stale quote is not returned in `quotes`
