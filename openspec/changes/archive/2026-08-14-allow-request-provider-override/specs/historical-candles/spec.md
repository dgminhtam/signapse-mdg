## MODIFIED Requirements

### Requirement: Candle symbols come from the enabled registry

The gateway MUST resolve the canonical symbol through the PostgreSQL-backed enabled symbol registry and resolve one immutable Provider Selection before accessing candle persistence or a provider. Omission of `provider` MUST select the Default Provider, and an explicit value MUST select the exact configured mapping regardless of default state.

#### Scenario: Enabled canonical symbol is requested without an override

- **WHEN** the requested symbol is enabled and `provider` is omitted
- **THEN** the gateway uses its Default Provider and provider symbol for persistence and provider routing
- **AND** those internal values are not exposed in the candle response

#### Scenario: Enabled canonical symbol supports the override

- **WHEN** the requested symbol is enabled and has a mapping matching the Provider Override
- **THEN** the gateway uses that Provider Selection for all persistence and provider operations
- **AND** the response remains provider-agnostic

#### Scenario: Enabled canonical symbol does not support the override

- **WHEN** the requested symbol is enabled but lacks a mapping matching the Provider Override
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `UNSUPPORTED_PROVIDER`
- **AND** sanitized error details identify the canonical symbol and requested provider
- **AND** no candle cache, persistence, or provider call is made

#### Scenario: Unknown or disabled symbol is requested

- **WHEN** the requested canonical symbol is absent from the enabled registry
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `UNSUPPORTED_SYMBOL`
- **AND** no Provider Mapping validation or candle provider call is made

### Requirement: Candle failures use stable gateway errors

The endpoint SHALL return the standard gateway error envelope and SHALL NOT expose database credentials, SQL, SDK exceptions, raw provider payloads, credentials, or stack traces.

#### Scenario: Request query shape is invalid

- **WHEN** a required candle query parameter is missing or malformed, or `provider` is empty or repeated
- **THEN** the gateway responds with a documented `400` gateway error
- **AND** an invalid provider query uses code `INVALID_PROVIDER`
- **AND** it does not return FastAPI's default `422` validation response

#### Scenario: Requested provider is unsupported for the asset

- **WHEN** the enabled asset has no mapping matching the requested Provider Identifier
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `UNSUPPORTED_PROVIDER`

#### Scenario: Candle persistence is unavailable

- **WHEN** registry or candle persistence cannot be queried or updated
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `DATABASE_UNAVAILABLE`

#### Scenario: Selected candle provider fails

- **WHEN** the selected provider SDK fails, provider configuration is unavailable, or its response cannot be safely normalized
- **THEN** the gateway responds with HTTP status `503`
- **AND** the error code is `PROVIDER_UNAVAILABLE`
- **AND** the gateway does not fall back to another Provider Mapping

### Requirement: Candle provider fills are routed by persisted provider mapping

The gateway SHALL use the immutable Provider Selection's `provider` and `provider_symbol` for persisted-candle reads and provider fills. Persisted rows MUST remain owned by their recorded provider identity, and the gateway MUST NOT read, relabel, merge, or fall back to rows owned by another mapping.

#### Scenario: Default-backed candle range requires provider data

- **WHEN** a candle request without a Provider Override requires a provider fill
- **THEN** the gateway delegates the missing range to the Default Provider's candle adapter using its provider symbol

#### Scenario: Override-backed candle range requires provider data

- **WHEN** a candle request with a supported Provider Override requires a provider fill
- **THEN** the gateway delegates the missing range to the selected provider's candle adapter using its provider symbol

#### Scenario: Same canonical series exists for two mappings

- **WHEN** persisted candle rows exist for two Provider Mappings of one canonical symbol and timeframe
- **THEN** the request reads and merges only rows belonging to its selected mapping
- **AND** rows owned by the other mapping are not relabeled or returned

#### Scenario: Default Provider is switched

- **WHEN** a canonical symbol is switched to another Default Provider
- **THEN** subsequent default candle reads and fills use the new provider identity
- **AND** existing candle rows retain their recorded provider and provider symbol

#### Scenario: Selected provider is unsupported operationally

- **WHEN** a candle request requires a provider fill
- **AND** no usable candle adapter is registered for the selected Provider Mapping
- **THEN** the gateway raises the sanitized `PROVIDER_UNAVAILABLE` boundary
- **AND** it does not fall back to a different provider

## ADDED Requirements

### Requirement: Forming candle cache is isolated by Provider Selection

The gateway MUST identify a forming candle cache entry by canonical symbol, Provider Identifier, provider symbol, and timeframe. A request MAY reuse a forming candle only when it resolves to the same Provider Mapping.

#### Scenario: Two mappings form the same canonical timeframe

- **WHEN** two Provider Mappings emit forming candles for the same canonical symbol and timeframe
- **THEN** the cache retains independent entries for the two mappings
- **AND** neither entry can satisfy a request selecting the other mapping

