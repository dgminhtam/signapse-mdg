## ADDED Requirements

### Requirement: WTI and ETF latest quotes are available through the existing endpoint

The gateway SHALL allow enabled WTI, SPY, and QQQ registry mappings to be requested through
`GET /v1/quotes` using the existing provider-agnostic quote contract.

#### Scenario: New Twelve Data symbols require refresh
- **WHEN** a valid quote request contains enabled `WTI`, `SPY`, or `QQQ` without a fresh cached
  quote
- **THEN** the gateway groups the provider symbols under `TWELVE_DATA`
- **AND** it requests their latest prices through the Twelve Data adapter
- **AND** each successful quote contains exactly `symbol`, `price`, and `receivedAt`

#### Scenario: Mixed provider quote request includes a new symbol
- **WHEN** a valid quote request contains a Binance-backed crypto symbol and one or more of `WTI`,
  `SPY`, or `QQQ`
- **THEN** the gateway routes each symbol through its persisted provider mapping
- **AND** a failure in one provider group does not discard successful quotes from another group

#### Scenario: Twelve Data entitlement is unavailable
- **WHEN** a WTI, SPY, or QQQ refresh requires Twelve Data and the provider cannot serve it
- **THEN** the affected symbol receives the existing `PROVIDER_UNAVAILABLE` or `DATA_STALE`
  symbol-level error according to cache state
- **AND** no provider-specific details are exposed
