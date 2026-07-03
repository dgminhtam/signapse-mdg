## ADDED Requirements

### Requirement: Provider adapters share identical internal normalization rules

Provider adapters SHALL use shared gateway-owned helper code for provider payload normalization when
the validation rule is identical across providers, while keeping provider-specific SDK types,
allowlists, interval identifiers, and error handling inside `app/providers/`.

#### Scenario: Equivalent Decimal payload rules are applied

- **WHEN** Binance, Twelve Data, or yfinance adapters normalize numeric price, OHLC, or volume
  payload fields with the same finite positive or non-negative Decimal rule
- **THEN** they use shared provider-owned normalization logic
- **AND** they preserve the existing accepted and rejected payload cases

#### Scenario: Provider-specific rules remain local

- **WHEN** a provider requires SDK-specific interval identifiers, supported-symbol allowlists, or
  response-shape handling
- **THEN** those rules remain in that provider adapter
- **AND** they are not exposed to domain, service, cache, database, or API modules

### Requirement: Provider candle duration uses canonical gateway timeframes

Provider REST candle adapters SHALL derive gateway candle duration from `app.domain.timeframes`
instead of maintaining duplicate per-provider duration maps for gateway timeframe values.

#### Scenario: Supported candle timeframe is requested

- **WHEN** a REST candle adapter receives a supported gateway provider interval
- **THEN** it uses the matching canonical timeframe duration for normalized candle close-time
  calculation
- **AND** existing candle response values remain unchanged

#### Scenario: Unsupported candle timeframe reaches an adapter

- **WHEN** a REST candle adapter receives an unknown provider interval
- **THEN** it preserves the existing provider-unavailable boundary

### Requirement: Provider setup cleanup preserves public behavior

Provider builder and route wiring cleanup SHALL preserve public API contracts, dependency override
entry points, SDK isolation, and configured provider policies.

#### Scenario: Provider clients are constructed after cleanup

- **WHEN** application dependencies build Binance, Twelve Data, or yfinance providers
- **THEN** existing settings, timeout policy, SDK isolation, and provider availability behavior are
  preserved

#### Scenario: Public market-data contracts are exercised after cleanup

- **WHEN** existing quote, candle, and WebSocket route tests run
- **THEN** response payloads, error boundaries, and stream event payloads remain unchanged
