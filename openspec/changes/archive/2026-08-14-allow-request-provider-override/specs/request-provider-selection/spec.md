## ADDED Requirements

### Requirement: Market-data requests accept one optional Provider Override

The gateway SHALL accept at most one case-sensitive `provider` query value on latest quote, historical candle, historical price, and WebSocket stream requests. The value SHALL apply to every requested asset, and omission SHALL select each asset's Default Provider.

#### Scenario: Provider Override is omitted
- **WHEN** a valid market-data request contains no `provider` query parameter
- **THEN** the gateway resolves every requested asset through its Default Provider
- **AND** existing clients retain their prior routing behavior

#### Scenario: Provider Override is supplied
- **WHEN** a valid market-data request contains exactly one non-empty `provider` value
- **THEN** the gateway treats that value as a case-sensitive Provider Identifier
- **AND** applies it to every asset in the request

#### Scenario: Provider Override is empty
- **WHEN** a request contains an empty or whitespace-only `provider` value
- **THEN** an HTTP request fails with status `400` and code `INVALID_PROVIDER`
- **AND** a WebSocket request closes with code `1008` and reason `INVALID_PROVIDER`
- **AND** the gateway does not access the registry, cache, persistence, or an upstream provider

#### Scenario: Provider Override is repeated
- **WHEN** a request contains more than one `provider` query value
- **THEN** an HTTP request fails with status `400` and code `INVALID_PROVIDER`
- **AND** a WebSocket request closes with code `1008` and reason `INVALID_PROVIDER`
- **AND** the gateway does not choose a first or last value

### Requirement: Provider Overrides are validated against each asset's mappings

The gateway MUST resolve a Provider Override only when the enabled canonical asset has a configured Provider Mapping with the exact Provider Identifier. Mapping eligibility SHALL NOT depend on whether the mapping is the Default Provider, and resolution SHALL NOT mutate registry state or fall back to another mapping.

#### Scenario: Non-default mapping is configured
- **WHEN** an enabled asset has a non-default Provider Mapping matching the requested Provider Identifier
- **THEN** the gateway resolves that mapping as the Provider Selection
- **AND** leaves the asset's Default Provider unchanged

#### Scenario: Asset lacks the requested mapping
- **WHEN** an enabled asset has no Provider Mapping matching the requested Provider Identifier
- **THEN** the asset fails with `UNSUPPORTED_PROVIDER`
- **AND** no cache, persistence, or upstream provider access occurs for that asset
- **AND** the gateway does not fall back to the Default Provider

#### Scenario: Canonical asset is unknown or disabled
- **WHEN** a requested canonical asset is unknown or disabled
- **THEN** the asset fails with `UNSUPPORTED_SYMBOL`
- **AND** Provider Mapping validation does not replace that error with `UNSUPPORTED_PROVIDER`

#### Scenario: Enabled asset lacks a Default Provider
- **WHEN** an enabled requested asset has no Default Provider because the registry invariant is broken
- **THEN** the operation fails with `DATABASE_UNAVAILABLE`
- **AND** an explicit Provider Override does not bypass the invalid registry state
- **AND** no cache, persistence, or upstream provider access occurs

#### Scenario: Provider Identifier is not mapped to any requested asset
- **WHEN** a syntactically valid Provider Identifier matches no requested asset mapping
- **THEN** each asset is evaluated independently as `UNSUPPORTED_PROVIDER`
- **AND** the gateway does not introduce a separate globally-known-provider validation

### Requirement: Provider Selection remains fixed for one operation

The gateway MUST resolve each requested asset to one immutable Provider Selection at the request or subscription boundary and MUST use that selection for every cache, persistence, provider, and downstream operation in its lifetime.

#### Scenario: Default changes during an HTTP request
- **WHEN** an asset's Default Provider changes after an HTTP request has resolved its Provider Selection
- **THEN** the in-flight request completes using its original selection
- **AND** a later request without an override uses the new Default Provider

#### Scenario: Default changes during a WebSocket subscription
- **WHEN** an asset's Default Provider changes while a WebSocket connection is active
- **THEN** the existing connection remains on its original selection until it closes
- **AND** a new connection without an override uses the new Default Provider

### Requirement: Market-data identity includes Provider Selection

The gateway MUST isolate normalized quotes, forming candles, persisted candle reads, and stream interests by canonical asset, Provider Identifier, and provider symbol, plus timeframe or channel where applicable. Operations MAY share state only when they resolve to the same Provider Mapping.

#### Scenario: Default and override select the same mapping
- **WHEN** a Default Provider request and a Provider Override request resolve to the same Provider Mapping
- **THEN** they may reuse the same eligible quote cache entry, forming candle, or upstream subscription

#### Scenario: Same asset is selected through two mappings
- **WHEN** concurrent requests or subscriptions select two different Provider Mappings for one canonical asset
- **THEN** their cached data, provider-owned candle reads, and stream interests remain independent
- **AND** neither selection can satisfy the other selection's request

#### Scenario: Default Provider is switched
- **WHEN** an asset's Default Provider changes from one mapping to another
- **THEN** new default requests do not reuse data owned by the previous mapping
- **AND** historical candle rows retain their recorded provider identity

### Requirement: Provider support and availability remain distinct

The gateway SHALL treat mapping existence as stable asset-provider support and SHALL treat adapter registration, credentials, timeout, rate limit, transport, upstream response, and payload validity as operational Provider Availability. Operational failure MUST NOT remove the mapping, produce `UNSUPPORTED_PROVIDER`, or trigger provider fallback.

#### Scenario: Configured provider is operationally unavailable
- **WHEN** a Provider Mapping exists but its adapter or upstream operation cannot serve the request
- **THEN** the gateway applies the existing sanitized `PROVIDER_UNAVAILABLE` behavior for that API
- **AND** it does not fall back to another Provider Mapping

#### Scenario: Same-selection cached quote remains usable
- **WHEN** a quote refresh fails but a quote cached for the same Provider Selection remains within the configured freshness boundary
- **THEN** the gateway may return that cached quote under the existing freshness rules
- **AND** it does not use a cached quote from another Provider Selection

#### Scenario: Same-selection cached quote is stale
- **WHEN** a quote refresh fails and the only same-selection cached quote exceeds the stale threshold
- **THEN** the asset fails with `DATA_STALE`
- **AND** another Provider Mapping is not consulted

### Requirement: Every exposed mapping supports the complete market-data surface

Every Provider Mapping returned by the gateway MUST be verified for latest quotes, every public historical candle timeframe, Historical Price Resolution, and WebSocket quote and candle delivery before release. The gateway MUST NOT maintain a second selectable-mapping allowlist or expose a mapping with only partial capability.

#### Scenario: Existing mapping passes verification
- **WHEN** a configured mapping passes verification across the complete market-data surface
- **THEN** it remains discoverable and eligible for Provider Override

#### Scenario: Existing mapping fails verification
- **WHEN** a configured mapping cannot satisfy one or more required market-data surfaces
- **THEN** the mapping is fixed or removed before release
- **AND** it is not hidden behind a route-specific or hard-coded selection rule

### Requirement: Provider Selection is observable but not public market data

The gateway SHALL include canonical symbol, provider, provider symbol, and selection mode `DEFAULT` or `OVERRIDE` in structured internal logs. Metrics MAY use provider and selection mode but MUST NOT use provider symbol as a label, and public market-data payloads MUST remain provider-agnostic.

#### Scenario: Override request is processed
- **WHEN** a market-data operation uses a Provider Override
- **THEN** structured telemetry identifies the resolved mapping and `OVERRIDE` mode
- **AND** the public data response or event does not add provider metadata

#### Scenario: Default request is processed
- **WHEN** a market-data operation omits Provider Override
- **THEN** structured telemetry identifies the resolved mapping and `DEFAULT` mode
- **AND** provider symbols do not create high-cardinality metric labels
