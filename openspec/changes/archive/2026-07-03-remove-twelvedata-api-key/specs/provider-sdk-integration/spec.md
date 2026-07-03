## MODIFIED Requirements

### Requirement: Twelve Data settings are deployment controlled

The gateway SHALL read Twelve Data provider configuration from typed environment settings, SHALL
support one or more configured Twelve Data API keys through `TWELVEDATA_API_KEYS` for Twelve Data
only, SHALL NOT support `TWELVEDATA_API_KEY`, and SHALL NOT commit usable Twelve Data credentials.

#### Scenario: Settings are loaded

- **WHEN** application settings are constructed
- **THEN** they include a Twelve Data API keys setting for comma-separated one-or-more keys
- **AND** they do not include a Twelve Data API key setting named `TWELVEDATA_API_KEY`
- **AND** they include a Twelve Data REST base URL setting
- **AND** they include a provider timeout setting usable by the Twelve Data adapter

#### Scenario: Placeholder configuration is distributed

- **WHEN** a contributor inspects repository environment examples
- **THEN** Twelve Data settings are documented with placeholder values only
- **AND** no usable Twelve Data API key is present
- **AND** the example uses `TWELVEDATA_API_KEYS` rather than `TWELVEDATA_API_KEY`

#### Scenario: Single key is configured through the plural setting

- **WHEN** deployment provides one value in `TWELVEDATA_API_KEYS`
- **THEN** Twelve Data REST and stream providers can be constructed with that key

#### Scenario: Multiple keys are configured

- **WHEN** deployment provides comma-separated Twelve Data API keys
- **THEN** the gateway builds an ordered de-duplicated effective key list for Twelve Data
- **AND** no other provider receives those keys

#### Scenario: Old single-key setting is provided

- **WHEN** deployment provides only `TWELVEDATA_API_KEY`
- **THEN** the gateway treats Twelve Data as unconfigured
- **AND** live Twelve Data provider fills fail through the sanitized provider-unavailable boundary
