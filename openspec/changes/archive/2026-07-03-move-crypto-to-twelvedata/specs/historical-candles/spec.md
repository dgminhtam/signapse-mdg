## MODIFIED Requirements

### Requirement: Forex historical candles are available through the existing endpoint

The gateway SHALL allow enabled `BTC/USD`, `ETH/USD`, `EUR/USD`, `GBP/USD`, `USD/JPY`,
`AUD/USD`, `XAU/USD`, `AAPL`, `TSLA`, `NVDA`, and `MSFT` registry mappings using provider
`TWELVE_DATA` to be requested through the existing `GET /v1/candles` contract.

#### Scenario: Twelve Data candle range requires provider data

- **WHEN** a valid Twelve Data-backed candle request contains one or more slots not available as
  persisted complete candles
- **THEN** the gateway requests the missing ranges from the Twelve Data adapter
- **AND** the successful response preserves the existing provider-agnostic candle shape

#### Scenario: Twelve Data candle range is fully persisted

- **WHEN** every requested Twelve Data-backed candle slot is available as a persisted complete
  candle
- **THEN** the gateway returns those persisted candles
- **AND** it makes no Twelve Data request
- **AND** the response can succeed without a configured Twelve Data API key

#### Scenario: Twelve Data is not configured

- **WHEN** a Twelve Data-backed candle request requires a live provider fill
- **AND** Twelve Data configuration is missing or unusable
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `PROVIDER_UNAVAILABLE`
- **AND** other provider-backed candle requests remain available

### Requirement: Candle provider fills are routed by persisted provider mapping

The gateway SHALL route every candle provider fill using the enabled symbol's persisted `provider`
and `provider_symbol` values.

#### Scenario: Binance-backed candle range requires provider data

- **WHEN** an enabled `BINANCE_SPOT` candle request requires a provider fill
- **THEN** the gateway delegates the missing range to the Binance candle adapter

#### Scenario: Twelve Data-backed candle range requires provider data

- **WHEN** an enabled `TWELVE_DATA` candle request requires a provider fill
- **THEN** the gateway delegates the missing range to the Twelve Data adapter

#### Scenario: Persisted provider is unsupported or unavailable

- **WHEN** a candle request requires a provider fill
- **AND** no usable candle adapter is registered for the persisted provider
- **THEN** the gateway raises the sanitized provider-unavailable boundary
- **AND** it does not fall back to a different provider
