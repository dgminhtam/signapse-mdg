## MODIFIED Requirements

### Requirement: YFINANCE historical candles use the existing endpoint

The gateway SHALL allow any enabled canonical asset whose active persisted mapping uses one of the
23 approved `YFINANCE` provider symbols to be requested through the existing `GET /v1/candles`
contract.

#### Scenario: YFINANCE candle range requires provider data

- **WHEN** a valid yfinance-backed candle request contains one or more slots not available as
  persisted complete candles
- **THEN** the gateway requests the missing ranges from the yfinance candle adapter
- **AND** the successful response preserves the existing provider-agnostic candle shape

#### Scenario: Inactive yfinance alternative is selected manually

- **WHEN** an approved inactive yfinance alternative becomes the asset's active persisted mapping
- **AND** its candle request requires a provider fill
- **THEN** the gateway requests the persisted yfinance provider symbol
- **AND** it does not read or fetch candles under the previous provider identity

#### Scenario: YFINANCE candle range is fully persisted

- **WHEN** every requested yfinance-backed candle slot is available as a persisted complete candle
- **THEN** the gateway returns those persisted candles
- **AND** it makes no yfinance request

#### Scenario: YFINANCE provider fails

- **WHEN** a yfinance-backed candle request requires a live provider fill
- **AND** yfinance or Yahoo Finance cannot provide a usable response
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `PROVIDER_UNAVAILABLE`
- **AND** Binance-backed and Twelve Data-backed candle requests remain available

