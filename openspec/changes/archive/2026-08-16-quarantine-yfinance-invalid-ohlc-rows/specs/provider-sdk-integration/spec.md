## MODIFIED Requirements

### Requirement: yfinance historical payloads are normalized internally

The yfinance adapter SHALL normalize historical provider payloads into repository-owned
candle models without exposing DataFrame objects, yfinance request options, or yfinance
exceptions outside `app/providers/`. It SHALL preserve strict batch validation for
structural and numeric failures while supporting row-level quarantine for an isolated
OHLC envelope violation when other valid rows remain.

#### Scenario: Valid yfinance history rows are returned

- **WHEN** yfinance returns valid history rows for `SI=F`, `BZ=F`, `NG=F`, `KC=F`, `SB=F`,
  `ZW=F`, `ZC=F`, `^GSPC`, `^NDX`, or `^DJI`
- **THEN** the adapter returns normalized `Candle` values keyed by the gateway symbol
  metadata
- **AND** each normalized candle uses `Decimal` OHLCV values and UTC datetimes

#### Scenario: Isolated OHLC envelope failure is quarantined

- **WHEN** a non-empty yfinance history payload contains a row whose `High` or `Low`
  is inconsistent with its `Open` or `Close`
- **AND** at least one other eligible row has valid required fields and values
- **THEN** the adapter returns the valid normalized candles
- **AND** it excludes the inconsistent row without changing its values
- **AND** it does not retry or select another provider

#### Scenario: Yfinance history response is batch-fatal or incomplete

- **WHEN** a yfinance history response is missing required time or OHLC fields,
  contains an invalid decimal, a non-finite value, a duplicate timestamp, negative
  volume, or leaves no valid row after OHLC-envelope quarantine
- **THEN** the adapter raises the provider-unavailable boundary
- **AND** it does not expose raw yfinance details outside the adapter
