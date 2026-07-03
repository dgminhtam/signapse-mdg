## ADDED Requirements

### Requirement: YFINANCE historical candles use the existing endpoint

The gateway SHALL allow enabled `XAG/USD`, `BRENT`, `NATGAS`, `COFFEE`, `SUGAR`, `WHEAT`,
`CORN`, `SPX`, `NDX`, and `DJI` registry mappings using provider `YFINANCE` to be requested
through the existing `GET /v1/candles` contract.

#### Scenario: YFINANCE candle range requires provider data

- **WHEN** a valid yfinance-backed candle request contains one or more slots not available as
  persisted complete candles
- **THEN** the gateway requests the missing ranges from the yfinance candle adapter
- **AND** the successful response preserves the existing provider-agnostic candle shape

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

### Requirement: YFINANCE candle fills are routed by persisted provider mapping

The gateway SHALL route yfinance candle provider fills using the enabled symbol's persisted
`provider` and `provider_symbol` values.

#### Scenario: YFINANCE candle range requires provider data

- **WHEN** an enabled `YFINANCE` candle request requires a provider fill
- **THEN** the gateway delegates the missing range to the yfinance candle adapter
- **AND** it uses the persisted yfinance provider symbol for the upstream request
- **AND** it does not fall back to a different provider

### Requirement: YFINANCE candles preserve gateway range semantics

The yfinance adapter SHALL map supported public timeframes to yfinance intervals, SHALL request
historical data using the gateway's half-open UTC range, and SHALL return only candles whose open
times satisfy `from <= open_time < to`.

#### Scenario: Half-open YFINANCE range is requested

- **WHEN** the gateway requests a yfinance range `[from,to)`
- **THEN** the adapter sends `start` equal to `from`
- **AND** it sends `end` equal to `to`
- **AND** it requests the yfinance interval matching the public timeframe

#### Scenario: Provider includes an ineligible boundary row

- **WHEN** yfinance returns a row whose open time equals or exceeds `to`
- **THEN** that row is not included in the normalized result
- **AND** no out-of-range candle is persisted or exposed

### Requirement: YFINANCE candle timestamps remain authoritative

The gateway MUST preserve valid yfinance candle open timestamps after UTC normalization and MUST
NOT shift them to fit a universal epoch-aligned grid.

#### Scenario: YFINANCE returns an offset candle timestamp

- **WHEN** a valid yfinance candle row opens at a timestamp that is not aligned to the UTC epoch
  grid for the requested timeframe
- **THEN** its normalized `openTime` remains that provider timestamp converted to UTC
- **AND** its `closeTime` is derived from that actual open time and requested timeframe duration

### Requirement: YFINANCE OHLCV rows are normalized strictly

The yfinance adapter SHALL convert valid history rows to repository-owned candle models using
`Decimal` values and UTC datetimes and MUST reject malformed, duplicate, invalid, or inconsistent
provider data.

#### Scenario: Valid YFINANCE rows are returned

- **WHEN** yfinance returns valid unique rows inside the requested range
- **THEN** the adapter normalizes open time, close time, OHLC values, and volume
- **AND** it ignores provider fields that are outside the gateway candle model

#### Scenario: YFINANCE row omits volume

- **WHEN** a valid yfinance row has no volume value or has a null volume value
- **THEN** the normalized candle volume is `Decimal("0")`
- **AND** the API serializes it as a fixed-point decimal string

#### Scenario: YFINANCE payload is invalid

- **WHEN** a yfinance row is malformed, has a non-finite or invalid OHLCV value, has inconsistent
  prices, has an invalid timestamp, duplicates an open time, or falls outside supported mapping
- **THEN** the adapter raises the sanitized provider-unavailable boundary
- **AND** no yfinance DataFrame, exception, or raw provider payload is exposed

### Requirement: Natural YFINANCE provider gaps are preserved

The gateway MUST preserve absent yfinance candle slots as gaps and MUST NOT fabricate OHLCV
candles for omitted provider data.

#### Scenario: Provider returns no candles for a valid range

- **WHEN** a valid yfinance-backed request covers eligible slots for which yfinance returns no rows
- **THEN** the gateway returns the valid available candles, which may be an empty list
- **AND** it does not create or persist synthetic candles

#### Scenario: Provider returns only part of a YFINANCE range

- **WHEN** yfinance omits one or more eligible slots but returns other valid rows
- **THEN** the gateway returns and persists only the valid eligible complete rows
- **AND** the omitted eligible slots remain absent
