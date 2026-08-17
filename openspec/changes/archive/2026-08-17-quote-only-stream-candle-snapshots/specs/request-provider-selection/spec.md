# Request-Scoped Provider Selection Specification Delta

## MODIFIED Requirements

### Requirement: Every exposed mapping supports the complete market-data surface

Every Provider Mapping returned by the gateway MUST be verified for latest quotes, every public
historical candle timeframe, Historical Price Resolution, and WebSocket quote delivery before
release. The WebSocket capability is quote-only; candle delivery is provided by the existing REST
`GET /v1/candles` operation. The gateway MUST NOT maintain a second selectable-mapping allowlist
or expose a mapping with only partial capability.

#### Scenario: Existing mapping passes verification

- **WHEN** a configured mapping passes verification across latest quotes, REST candles, Historical
  Price Resolution, and WebSocket quote delivery
- **THEN** it remains discoverable and eligible for Provider Override

#### Scenario: Existing mapping fails verification

- **WHEN** a configured mapping cannot satisfy one or more required market-data surfaces
- **THEN** the mapping is fixed or removed before release
- **AND** it is not hidden behind a route-specific or hard-coded selection rule
