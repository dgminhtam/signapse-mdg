## Purpose

Defines the historical price lookup API that returns the closest eligible completed candle price
for a requested instant through one immutable Provider Selection and a fixed common resolution
ladder.

## Requirements

### Requirement: Historical price can be requested by canonical symbol and instant

The gateway SHALL expose `GET /v1/historical-price` for one canonical `symbol`, one UTC `at`
timestamp, and at most one optional case-sensitive `provider` value. It SHALL NOT require or accept
a public timeframe parameter for this lookup.

#### Scenario: Valid historical price request uses the default

- **WHEN** a client requests an enabled canonical symbol and valid UTC `at` timestamp without
  `provider`
- **THEN** the gateway responds with HTTP status `200`
- **AND** resolves the lookup through the symbol's Default Provider
- **AND** the response represents that canonical symbol

#### Scenario: Valid historical price request uses an override

- **WHEN** a client requests an enabled canonical symbol, valid UTC `at`, and a configured
  non-default Provider Mapping
- **THEN** the gateway responds with HTTP status `200`
- **AND** uses that mapping throughout every Historical Price Resolution attempt

#### Scenario: Timeframe is not part of the public contract

- **WHEN** a client requests historical price
- **THEN** the client supplies no timeframe value
- **AND** the gateway uses the common canonical resolution sequence `1m`, `5m`, `1h`, then `1d`
- **AND** the successful response identifies the selected resolution

### Requirement: Historical price uses provider-specific completed-candle resolution

The gateway SHALL resolve historical price through the existing historical-candle flow using the
immutable Provider Selection and the fixed canonical timeframe sequence `1m`, `5m`, `1h`, then
`1d`. It SHALL return the close of the nearest eligible completed candle selected by that policy
at or before `at`, MUST require the selected candle's close time to be at or before `at`, and MUST
NOT change provider while trying another timeframe. The resolver SHALL try timeframes sequentially
and SHALL make no more than four attempts.

#### Scenario: Finest eligible completed candle is available

- **WHEN** the selected provider's `1m` attempt contains an eligible candle whose close time is at
  or before `at`
- **THEN** the gateway returns that candle's close price
- **AND** resolves `pricedAt` as that candle's open time
- **AND** resolves `resolution` as `1m`
- **AND** makes no `5m`, `1h`, or `1d` attempt

#### Scenario: Finer timeframe returns valid no-data

- **WHEN** an attempted timeframe returns no eligible candle because of provider retention,
  natural provider gaps, or a closed session
- **THEN** the resolver tries the next timeframe in the fixed sequence
- **AND** every attempt uses the same Provider Selection
- **AND** it does not synthesize a candle from another timeframe

#### Scenario: Coarser completed candle is selected

- **WHEN** `1m` and `5m` return no eligible candle
- **AND** `1h` contains an eligible candle whose close time is at or before `at`
- **THEN** the gateway returns that candle's close price
- **AND** resolves `pricedAt` as that candle's open time
- **AND** resolves `resolution` as `1h`

#### Scenario: Resolution attempts are bounded and sequential

- **WHEN** no eligible candle is returned by an attempted timeframe
- **THEN** the gateway attempts timeframes in the order `1m`, `5m`, `1h`, `1d`
- **AND** it stops at the first eligible result
- **AND** it makes no more than four attempts

#### Scenario: Coarser candle would look ahead

- **WHEN** a coarser candle opens at or before `at` but closes after `at`
- **THEN** that candle is ineligible for Historical Price Resolution
- **AND** the gateway does not use its close price
- **AND** the gateway may continue to the next permitted timeframe

#### Scenario: Forming candle is excluded

- **WHEN** a returned candle is not complete at resolution time
- **THEN** the gateway does not select that candle
- **AND** it selects the nearest earlier eligible completed candle if one exists

#### Scenario: Closed session resolves to a previous eligible candle

- **WHEN** a client requests a past instant outside the symbol's market session
- **AND** a previous eligible completed candle is available under the resolution policy
- **THEN** the gateway resolves `pricedAt` as that candle's open time
- **AND** returns that candle's close price

#### Scenario: Historical candle flow is reused

- **WHEN** a candidate candle is absent from persistence
- **THEN** the gateway uses the existing historical-candle provider-fill path with the immutable
  Provider Selection
- **AND** applies the existing market-session, range, normalization, persistence, and cache
  behavior

#### Scenario: Selected provider fails operationally

- **WHEN** an attempted timeframe fails because of provider configuration, credentials, timeout,
  rate limit, transport, or payload validity
- **THEN** the lookup fails with `PROVIDER_UNAVAILABLE`
- **AND** the failure is not masked by trying a coarser timeframe or another Provider Mapping

### Requirement: Historical price response is minimal and provider-agnostic

A successful historical price response SHALL contain exactly `symbol`, `price`, `pricedAt`, and
`resolution`. `price` SHALL be the selected completed candle close serialized as a decimal string,
`pricedAt` SHALL be that candle's open time serialized as an ISO-8601 UTC timestamp, and
`resolution` SHALL be the selected canonical timeframe.

#### Scenario: Successful response fields are serialized

- **WHEN** the gateway resolves an eligible completed candle at or before the requested instant
- **THEN** the response contains exactly `symbol`, `price`, `pricedAt`, and `resolution`
- **AND** `resolution` is one of `1m`, `5m`, `1h`, or `1d`
- **AND** it does not contain OHLC fields, volume, asset class, provider identity, provider symbol,
  freshness, fallback reason, or source metadata

#### Scenario: Decimal price is serialized as a string

- **WHEN** the selected candle close is returned
- **THEN** `price` is serialized as a fixed-point decimal string without binary floating-point
  conversion or scientific notation

#### Scenario: Priced timestamp identifies the selected candle

- **WHEN** the resolution policy selects an eligible completed candle
- **THEN** `pricedAt` equals the selected candle's open time
- **AND** it may precede the finest-timeframe bucket containing `at`

#### Scenario: Resolution identifies fallback precision

- **WHEN** the gateway selects a candle coarser than `1m`
- **THEN** `resolution` equals that candle's canonical timeframe
- **AND** the gateway does not claim that the result is a one-minute price

### Requirement: Historical price failures use stable gateway errors

The endpoint SHALL return the standard gateway error envelope and SHALL NOT expose database
credentials, SQL, SDK exceptions, raw provider payloads, credentials, or stack traces.

#### Scenario: Symbol is unknown or disabled

- **WHEN** the requested canonical symbol is absent from the enabled registry
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `UNSUPPORTED_SYMBOL`

#### Scenario: Provider query is malformed

- **WHEN** `provider` is empty, whitespace-only, or repeated
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_PROVIDER`
- **AND** no registry, persistence, or provider operation occurs

#### Scenario: Provider is unsupported for the asset

- **WHEN** the enabled asset has no mapping matching the requested Provider Identifier
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `UNSUPPORTED_PROVIDER`
- **AND** sanitized error details identify the canonical symbol and requested provider
- **AND** no persistence or provider operation occurs

#### Scenario: Timestamp is missing or malformed

- **WHEN** `at` is missing, empty, invalid, or not explicitly UTC
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Timestamp is in the future

- **WHEN** `at` is later than the single UTC instant captured for the request
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`
- **AND** it performs no persistence or provider operation

#### Scenario: No historical price is available before the requested instant

- **WHEN** every timeframe in the fixed resolution sequence returns no eligible completed candle
- **THEN** the gateway responds with HTTP status `404`
- **AND** the error code is `PRICE_NOT_FOUND`

#### Scenario: Persistence is unavailable

- **WHEN** registry or candle persistence cannot be queried or updated
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `DATABASE_UNAVAILABLE`

#### Scenario: Selected provider fails

- **WHEN** the selected candle provider fails operationally during Historical Price Resolution
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `PROVIDER_UNAVAILABLE`
- **AND** no coarser-timeframe or cross-provider fallback masks the failure

### Requirement: Historical price values are independent of display precision

The gateway SHALL retain the selected completed candle close at its persisted precision and SHALL
serialize the public historical `price` rounded with `ROUND_HALF_UP` and padded to exactly the
symbol's `price_display_decimals`.

#### Scenario: Selected close exceeds display decimals

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** the selected completed candle close is `Decimal("2934.5678")`
- **THEN** the historical price response contains `"price":"2934.57"`
- **AND** the persisted candle close remains unchanged

#### Scenario: Selected close is exactly halfway

- **WHEN** a symbol has `price_display_decimals` value `2`
- **AND** the selected completed candle close is `Decimal("2934.565")`
- **THEN** the historical price response contains `"price":"2934.57"`

#### Scenario: Historical price response remains minimal

- **WHEN** a historical price is returned successfully
- **THEN** the response continues to contain exactly `symbol`, `price`, `pricedAt`, and `resolution`
- **AND** it does not contain `priceDisplayDecimals`

### Requirement: Provider adapters distinguish valid no-data from operational failure

Provider adapters participating in Historical Price Resolution SHALL return an empty candle list
for a valid requested range with no available data, including recognized retention or no-data
responses. They SHALL raise the existing sanitized provider-unavailable boundary for operational,
authentication, quota, transport, timeout, malformed-payload, or invalid-response failures.

#### Scenario: Provider returns valid no-data

- **WHEN** an attempted provider timeframe has no rows for the requested eligible range
- **THEN** the adapter returns an empty candle list
- **AND** Historical Price Resolution may try the next canonical timeframe

#### Scenario: Provider reports an operational failure

- **WHEN** an attempted provider timeframe fails because the provider cannot serve the request
- **THEN** the adapter raises the sanitized provider-unavailable boundary
- **AND** Historical Price Resolution does not try a coarser timeframe
