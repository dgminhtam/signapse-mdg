## MODIFIED Requirements

### Requirement: Stream interests are routed by persisted provider mapping

The gateway SHALL route each validated stream interest through the provider and provider symbol
resolved from the enabled canonical symbol's single active normalized mapping. It MUST use the same
active selection as quote, candle, and backfill routes and MUST NOT use an inactive mapping.

#### Scenario: Mixed-provider subscription is accepted

- **WHEN** a client subscribes to enabled canonical symbols backed by one or more active provider
  mappings in one `/v1/stream` request
- **THEN** the gateway registers quote and candle interests for every requested canonical symbol
- **AND** it routes each upstream interest through that symbol's active provider mapping

#### Scenario: Active provider mapping changes before a new subscription

- **WHEN** a symbol's active mapping changes before a subsequent client subscription is resolved
- **THEN** the new interest uses the newly active provider and provider symbol
- **AND** no inactive mapping is selected as fallback

#### Scenario: Unsupported stream provider mapping is requested

- **WHEN** an enabled symbol's active mapping names a provider with no configured stream adapter
- **THEN** the gateway rejects the affected subscription with sanitized `PROVIDER_UNAVAILABLE`
- **AND** it does not fall back to another provider

#### Scenario: Provider failure is isolated to affected interests

- **WHEN** one upstream provider emits an error signal for its active interests
- **THEN** downstream status events identify only the affected symbols and channels
- **AND** unaffected provider interests can continue receiving normalized events
