## ADDED Requirements

### Requirement: Forex historical candles are available through the existing endpoint

The gateway SHALL allow enabled `EUR/USD`, `GBP/USD`, `USD/JPY`, and `AUD/USD` registry mappings
using provider `TWELVE_DATA` to be requested through the existing `GET /v1/candles` contract.

#### Scenario: Forex candle range requires provider data

- **WHEN** a valid Forex candle request contains one or more slots not available as persisted
  complete candles
- **THEN** the gateway requests the missing ranges from the Twelve Data Forex adapter
- **AND** the successful response preserves the existing provider-agnostic candle shape

#### Scenario: Forex candle range is fully persisted

- **WHEN** every requested Forex candle slot is available as a persisted complete candle
- **THEN** the gateway returns those persisted candles
- **AND** it makes no Twelve Data request
- **AND** the response can succeed without a configured Twelve Data API key

#### Scenario: Twelve Data is not configured

- **WHEN** a Forex candle request requires a live provider fill
- **AND** Twelve Data configuration is missing or unusable
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `PROVIDER_UNAVAILABLE`
- **AND** Binance-backed crypto candle requests remain available

### Requirement: Candle provider fills are routed by persisted provider mapping

The gateway SHALL route every candle provider fill using the enabled symbol's persisted `provider`
and `provider_symbol` values.

#### Scenario: Crypto candle range requires provider data

- **WHEN** an enabled `BINANCE_SPOT` candle request requires a provider fill
- **THEN** the gateway delegates the missing range to the Binance candle adapter

#### Scenario: Forex candle range requires provider data

- **WHEN** an enabled `TWELVE_DATA` candle request requires a provider fill
- **THEN** the gateway delegates the missing range to the Twelve Data Forex adapter

#### Scenario: Persisted provider is unsupported or unavailable

- **WHEN** a candle request requires a provider fill
- **AND** no usable candle adapter is registered for the persisted provider
- **THEN** the gateway raises the sanitized provider-unavailable boundary
- **AND** it does not fall back to a different provider

### Requirement: Twelve Data Forex candles preserve gateway range semantics

The Twelve Data adapter SHALL map supported public timeframes to Twelve Data intervals, SHALL
request UTC ascending time-series data bounded to the gateway's half-open range, and SHALL return
only candles whose open times satisfy `from <= open_time < to`.

#### Scenario: Half-open Forex range is requested

- **WHEN** the gateway requests a Twelve Data range `[from,to)`
- **THEN** the adapter sends `start_date` equal to `from`
- **AND** it sends `end_date` equal to the final eligible candle open time before `to`
- **AND** it sends `outputsize` equal to the expected gateway slot count
- **AND** it requests UTC timestamps in ascending order

#### Scenario: Provider includes an ineligible boundary row

- **WHEN** Twelve Data returns a row whose open time equals or exceeds `to`
- **THEN** that row is not included in the normalized result
- **AND** no out-of-range candle is persisted or exposed

### Requirement: Forex volume absence is normalized explicitly

The Twelve Data Forex adapter SHALL represent an omitted or null provider volume as exact decimal
zero because the existing public and persistence candle contracts require a non-null volume.

#### Scenario: Forex row omits volume

- **WHEN** a valid Twelve Data Forex OHLC row has no `volume` field or has a null `volume`
- **THEN** the normalized candle volume is `Decimal("0")`
- **AND** the API serializes it as a fixed-point decimal string

#### Scenario: Forex row supplies malformed volume

- **WHEN** a Twelve Data row supplies a non-null volume that is non-decimal, negative, or non-finite
- **THEN** the adapter raises the sanitized provider-unavailable boundary

### Requirement: Natural Forex market gaps are not synthesized

The gateway MUST preserve absent Twelve Data Forex candle slots as gaps and MUST NOT fabricate
OHLCV candles for closed sessions or omitted provider data.

#### Scenario: Provider returns no candles for a closed-market range

- **WHEN** a valid Forex request covers slots for which Twelve Data returns no rows
- **THEN** the gateway returns the valid available candles, which may be an empty list
- **AND** it does not create or persist synthetic candles

#### Scenario: Provider returns only part of a requested Forex range

- **WHEN** Twelve Data omits one or more expected slots but returns other valid rows
- **THEN** the gateway returns and persists only the valid complete rows
- **AND** the omitted slots remain absent

## MODIFIED Requirements

### Requirement: Initial candle timeframes are explicitly supported

The gateway SHALL support public timeframes `1m`, `5m`, `15m`, `1h`, and `1d` and SHALL map them to
the corresponding interval inside the selected provider adapter boundary.

#### Scenario: Supported timeframe is requested

- **WHEN** a client requests `1m`, `5m`, `15m`, `1h`, or `1d`
- **THEN** the gateway resolves the corresponding interval for the symbol's persisted provider

#### Scenario: Unsupported timeframe is requested

- **WHEN** a client requests any other timeframe
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `UNSUPPORTED_TIMEFRAME`
- **AND** the sanitized error details identify the rejected timeframe

### Requirement: Closed candles are reused from PostgreSQL

The gateway SHALL query persisted complete candles before calling the selected provider and SHALL
identify missing timeframe slots within the requested range.

#### Scenario: Complete range is persisted

- **WHEN** every requested candle slot is available as a persisted complete candle
- **THEN** the gateway returns the persisted candles
- **AND** it makes no provider candle request

#### Scenario: Part of the range is missing

- **WHEN** one or more contiguous sections of the requested range are absent from persistence
- **THEN** the gateway requests only those missing sections from the provider selected by the
  symbol's persisted mapping
- **AND** it merges valid fetched candles with persisted candles by open time

#### Scenario: Provider omits an expected slot

- **WHEN** the selected provider returns no candle for an expected missing slot
- **THEN** the gateway returns the valid available candles after the fill attempt
- **AND** it does not synthesize an OHLCV candle

### Requirement: Database work does not span provider waits

The candle flow MUST close its database read session before awaiting the selected provider and
SHALL perform upserts in a separate short transaction.

#### Scenario: Cache miss requires provider data

- **WHEN** a repository read identifies a missing candle range
- **THEN** the read session and transaction are closed before the provider call begins
- **AND** a separate transaction is used to persist complete fetched candles

### Requirement: Candle failures use stable gateway errors

The endpoint SHALL return the standard gateway error envelope and SHALL NOT expose database
credentials, SQL, SDK exceptions, raw provider payloads, credentials, or stack traces.

#### Scenario: Request query shape is invalid

- **WHEN** a required candle query parameter is missing or malformed
- **THEN** the gateway responds with a documented `400` gateway error
- **AND** it does not return FastAPI's default `422` validation response

#### Scenario: Candle persistence is unavailable

- **WHEN** registry or candle persistence cannot be queried or updated
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `DATABASE_UNAVAILABLE`

#### Scenario: Selected candle provider fails

- **WHEN** the selected provider SDK fails, provider configuration is unavailable, or its response
  cannot be safely normalized
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `PROVIDER_UNAVAILABLE`
