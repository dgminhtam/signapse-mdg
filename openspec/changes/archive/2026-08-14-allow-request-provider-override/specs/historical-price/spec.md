## MODIFIED Requirements

### Requirement: Historical price can be requested by canonical symbol and instant

The gateway SHALL expose `GET /v1/historical-price` for one canonical `symbol`, one UTC `at` timestamp, and at most one optional case-sensitive `provider` value. It SHALL NOT require or accept a public timeframe parameter for this lookup.

#### Scenario: Valid historical price request uses the default

- **WHEN** a client requests an enabled canonical symbol and valid UTC `at` timestamp without `provider`
- **THEN** the gateway responds with HTTP status `200`
- **AND** resolves the lookup through the symbol's Default Provider
- **AND** the response represents that canonical symbol

#### Scenario: Valid historical price request uses an override

- **WHEN** a client requests an enabled canonical symbol, valid UTC `at`, and a configured non-default Provider Mapping
- **THEN** the gateway responds with HTTP status `200`
- **AND** uses that mapping throughout Historical Price Resolution

#### Scenario: Timeframe is not part of the public contract

- **WHEN** a client requests historical price
- **THEN** the client supplies no timeframe value
- **AND** the gateway uses its internal provider-specific Historical Price Resolution policy

### Requirement: Historical price uses provider-specific completed-candle resolution

The gateway SHALL resolve historical price through the existing historical-candle flow using the immutable Provider Selection and the provider-specific timeframe sequence owned by Historical Price Resolution. It SHALL return the close of the nearest eligible completed candle selected by that policy at or before `at`, MUST require the selected candle's close time to be at or before `at`, and MUST NOT change provider while trying another timeframe.

#### Scenario: Finest eligible completed candle is available

- **WHEN** the selected provider's finest attempted timeframe contains an eligible candle whose close time is at or before `at`
- **THEN** the gateway returns that candle's close price
- **AND** resolves `pricedAt` as that candle's open time

#### Scenario: Finer timeframe is unavailable because of provider retention

- **WHEN** the selected provider returns no eligible data for a finer timeframe because the requested instant is outside its retained history
- **THEN** the resolver may try the next coarser timeframe in its provider-specific policy
- **AND** every attempt uses the same Provider Selection

#### Scenario: Coarser candle would look ahead

- **WHEN** a coarser candle opens at or before `at` but closes after `at`
- **THEN** that candle is ineligible for Historical Price Resolution
- **AND** the gateway does not use its close price

#### Scenario: Closed session resolves to a previous eligible candle

- **WHEN** a client requests a past instant outside the symbol's market session
- **AND** a previous eligible completed candle is available under the resolution policy
- **THEN** the gateway resolves `pricedAt` as that candle's open time
- **AND** returns that candle's close price

#### Scenario: Historical candle flow is reused

- **WHEN** a candidate candle is absent from persistence
- **THEN** the gateway uses the existing historical-candle provider-fill path with the immutable Provider Selection
- **AND** applies the existing market-session, range, normalization, persistence, and gap behavior

#### Scenario: Selected provider fails operationally

- **WHEN** an attempted timeframe fails because of provider configuration, credentials, timeout, rate limit, transport, or payload validity
- **THEN** the lookup fails with `PROVIDER_UNAVAILABLE`
- **AND** the failure is not masked by trying a coarser timeframe or another Provider Mapping

### Requirement: Historical price response is minimal and provider-agnostic

A successful historical price response SHALL contain exactly `symbol`, `price`, and `pricedAt`. `price` SHALL be the selected completed candle close serialized as a decimal string, and `pricedAt` SHALL be that candle's open time serialized as an ISO-8601 UTC timestamp.

#### Scenario: Successful response fields are serialized

- **WHEN** the gateway resolves an eligible completed candle at or before the requested instant
- **THEN** the response contains exactly `symbol`, `price`, and `pricedAt`
- **AND** it does not contain timeframe, OHLC fields, volume, asset class, provider identity, provider symbol, freshness, or source metadata

#### Scenario: Decimal price is serialized as a string

- **WHEN** the selected candle close is returned
- **THEN** `price` is serialized as a fixed-point decimal string without binary floating-point conversion or scientific notation

#### Scenario: Priced timestamp identifies the selected candle

- **WHEN** the resolution policy selects an eligible completed candle
- **THEN** `pricedAt` equals the selected candle's open time
- **AND** it may precede the finest-timeframe bucket containing `at`

### Requirement: Historical price failures use stable gateway errors

The endpoint SHALL return the standard gateway error envelope and SHALL NOT expose database credentials, SQL, SDK exceptions, raw provider payloads, credentials, or stack traces.

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

#### Scenario: No historical price is available before the requested instant

- **WHEN** every timeframe permitted by the selected provider's resolution policy returns no eligible completed candle
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

