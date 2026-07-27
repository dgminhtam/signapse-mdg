## MODIFIED Requirements

### Requirement: Candle provider fills are routed by persisted provider mapping

The gateway SHALL resolve each enabled canonical symbol through its single active normalized
provider mapping and SHALL use that resolved `provider` and `provider_symbol` for persisted-candle
reads and provider fills. It MUST NOT use an inactive mapping or automatic fallback.

#### Scenario: Binance-backed candle range requires provider data

- **WHEN** an enabled symbol's active `BINANCE_SPOT` mapping requires a provider fill
- **THEN** the gateway delegates the missing range to the Binance candle adapter using the active
  provider symbol

#### Scenario: Twelve Data-backed candle range requires provider data

- **WHEN** an enabled symbol's active `TWELVE_DATA` mapping requires a provider fill
- **THEN** the gateway delegates the missing range to the Twelve Data adapter using the active
  provider symbol

#### Scenario: Active provider mapping is switched

- **WHEN** a canonical symbol is switched to another active provider mapping
- **THEN** subsequent candle reads and fills use the newly active provider identity
- **AND** existing candle rows retain their recorded provider and provider symbol
- **AND** rows owned by the previously active mapping are not relabeled as the new provider's rows

#### Scenario: Persisted provider is unsupported or unavailable

- **WHEN** a candle request requires a provider fill
- **AND** no usable candle adapter is registered for the active provider
- **THEN** the gateway raises the sanitized provider-unavailable boundary
- **AND** it does not fall back to a different provider
