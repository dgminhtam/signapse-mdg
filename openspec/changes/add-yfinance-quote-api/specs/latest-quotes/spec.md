## ADDED Requirements

### Requirement: yfinance latest quotes are available through the existing endpoint

The gateway SHALL allow the ten enabled seeded `YFINANCE` symbols to be requested through
`GET /v1/quotes` using the existing provider-agnostic response contract.

#### Scenario: yfinance commodity symbols require refresh

- **WHEN** `XAG/USD`, `BRENT`, `NATGAS`, `COFFEE`, `SUGAR`, `WHEAT`, or `CORN` lacks a reusable
  cached quote
- **THEN** the gateway requests its persisted yfinance provider symbol through the yfinance quote
  adapter
- **AND** a successful result contains exactly `symbol`, `price`, and `receivedAt`

#### Scenario: yfinance stock index symbols require refresh

- **WHEN** `SPX`, `NDX`, or `DJI` lacks a reusable cached quote
- **THEN** the gateway requests `^GSPC`, `^NDX`, or `^DJI` respectively through the yfinance quote
  adapter
- **AND** a successful result contains the canonical gateway symbol rather than the Yahoo ticker

#### Scenario: Mixed request includes yfinance and existing providers

- **WHEN** a quote request mixes enabled Binance, Twelve Data, and yfinance symbols
- **THEN** each provider group is refreshed independently
- **AND** successful quotes and symbol-level errors preserve the first occurrence request order

#### Scenario: One yfinance symbol is unavailable

- **WHEN** yfinance returns a valid latest price for one requested symbol but another requested
  symbol is missing, invalid, rate-limited, or fails to load
- **THEN** the valid symbol appears in `quotes`
- **AND** the affected symbol receives `PROVIDER_UNAVAILABLE` when no reusable cached quote exists
- **AND** the response status remains `200`

#### Scenario: yfinance quote is reused from cache

- **WHEN** a requested yfinance quote is within `QUOTE_CACHE_TTL_SECONDS`
- **THEN** the cached quote is returned
- **AND** no yfinance provider request is made for that symbol

#### Scenario: yfinance market is closed

- **WHEN** `regularMarketPrice` contains the last valid regular-session price while the instrument's
  market is closed
- **THEN** the gateway returns that price using gateway receive time as `receivedAt`
- **AND** it does not claim that `receivedAt` is the provider trade time

## MODIFIED Requirements

### Requirement: Provider prices are normalized without floating point

The gateway SHALL validate provider prices as finite positive decimal values and SHALL expose a
minimal provider-agnostic public quote without leaking provider payload or routing metadata.

#### Scenario: Valid provider prices are returned

- **WHEN** Binance, Twelve Data, or yfinance returns valid prices for requested provider symbols
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
