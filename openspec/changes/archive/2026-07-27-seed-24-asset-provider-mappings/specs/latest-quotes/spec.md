## MODIFIED Requirements

### Requirement: yfinance latest quotes are available through the existing endpoint

The gateway SHALL allow any enabled canonical asset whose active persisted mapping uses one of the
23 approved `YFINANCE` provider symbols to be requested through `GET /v1/quotes` using the existing
provider-agnostic response contract.

#### Scenario: Active yfinance catalog symbol requires refresh

- **WHEN** an enabled asset with an active yfinance mapping lacks a reusable cached quote
- **THEN** the gateway requests its persisted provider symbol through the yfinance quote adapter
- **AND** a successful result contains exactly `symbol`, `price`, and `receivedAt`

#### Scenario: Inactive yfinance alternative is selected manually

- **WHEN** an approved inactive yfinance alternative becomes the asset's active persisted mapping
- **THEN** a subsequent quote refresh uses that yfinance provider symbol
- **AND** it does not fall back to the previous provider

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

