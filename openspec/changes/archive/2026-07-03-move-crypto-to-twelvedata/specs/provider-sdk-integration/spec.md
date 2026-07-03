## MODIFIED Requirements

### Requirement: Twelve Data Forex payloads are normalized internally

The Twelve Data adapter foundation SHALL normalize supported Twelve Data provider payloads into
repository-owned domain-compatible primitives without exposing SDK response structures outside
`app/providers/`.

#### Scenario: Latest Twelve Data prices are requested through the adapter

- **WHEN** the adapter receives provider symbols for `BTC/USD`, `ETH/USD`, `EUR/USD`, `GBP/USD`,
  `USD/JPY`, `AUD/USD`, `XAU/USD`, `AAPL`, `TSLA`, `NVDA`, or `MSFT`
- **THEN** it can request Twelve Data latest prices for those provider symbols
- **AND** it returns finite positive prices as `Decimal` values keyed by provider symbol

#### Scenario: Twelve Data time-series candles are requested through the adapter

- **WHEN** the adapter receives a supported gateway timeframe for a supported Twelve Data symbol
- **THEN** it maps the timeframe to the corresponding Twelve Data interval
- **AND** it can normalize returned OHLCV rows into internal candle-compatible values

#### Scenario: SDK response is invalid or incomplete

- **WHEN** a Twelve Data response is missing required price, time, or OHLC fields, contains an
  invalid decimal, or indicates a provider error
- **THEN** the adapter reports the affected provider symbol as unavailable or raises the
  provider-unavailable boundary
- **AND** it does not expose raw provider error details outside the adapter

## ADDED Requirements

### Requirement: Twelve Data adapter supports crypto instruments

The gateway SHALL use the existing Twelve Data REST and stream adapter boundaries for `BTC/USD`
and `ETH/USD` when those canonical symbols are mapped to `TWELVE_DATA`.

#### Scenario: Valid crypto instrument is requested
- **WHEN** the adapter receives `BTC/USD` or `ETH/USD`
- **THEN** it invokes the SDK with the matching provider symbol

#### Scenario: Crypto instrument is outside the allowlist
- **WHEN** an unsupported Twelve Data crypto symbol is requested
- **THEN** no provider request is made for that symbol
