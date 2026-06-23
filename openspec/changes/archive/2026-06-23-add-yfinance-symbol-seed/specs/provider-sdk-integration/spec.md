## ADDED Requirements

### Requirement: yfinance dependency is available for provider code

The gateway SHALL include a locked `yfinance` package dependency for future provider adapter work
and SHALL keep yfinance usage behind repository-owned provider boundaries.

#### Scenario: Project dependencies are installed

- **WHEN** project dependencies are installed from the locked dependency set
- **THEN** the `yfinance` package is available to provider adapter code
- **AND** no yfinance package type is required by domain, service, cache, database, or API modules

#### Scenario: yfinance imports are inspected

- **WHEN** production modules outside `app/providers/` are analyzed
- **THEN** they contain no imports of yfinance modules, clients, models, or exceptions

### Requirement: yfinance market-data routing remains out of scope

This change SHALL NOT implement or wire yfinance latest quote, historical candle, or WebSocket
market-data routing.

#### Scenario: Public market-data routes are used after yfinance seed

- **WHEN** enabled `YFINANCE` registry rows exist
- **THEN** public quote, candle, and WebSocket routes make no yfinance provider calls
- **AND** existing Binance and Twelve Data market-data behavior remains unchanged

#### Scenario: Application starts after dependency installation

- **WHEN** the gateway application starts after this change
- **THEN** no yfinance client, session, WebSocket, or background task is opened during startup
