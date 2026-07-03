## ADDED Requirements

### Requirement: yfinance historical candles use the public download API

The gateway SHALL use the locked `yfinance` package behind a repository-owned adapter to fetch
historical candles for enabled `YFINANCE` provider symbols.

#### Scenario: YFINANCE time-series candles are requested through the adapter

- **WHEN** the adapter receives a supported gateway timeframe for a supported yfinance symbol
- **THEN** it maps the timeframe to the corresponding yfinance interval
- **AND** it invokes the yfinance historical download API with the persisted provider symbol
- **AND** it passes explicit `start`, `end`, `interval`, `timeout`, and session controls

#### Scenario: YFINANCE symbol is outside the allowlist

- **WHEN** an unsupported yfinance provider symbol is requested
- **THEN** no provider request is made for that symbol
- **AND** the adapter raises or reports the sanitized provider-unavailable boundary

### Requirement: yfinance REST work does not block the event loop

The gateway MUST execute synchronous yfinance REST operations outside the ASGI event loop and
SHALL serialize access to the shared yfinance session used by the adapter.

#### Scenario: yfinance history operation is slow

- **WHEN** a synchronous yfinance history operation waits for network I/O
- **THEN** unrelated async gateway work can continue on the event loop

#### Scenario: Concurrent yfinance calls reach the adapter

- **WHEN** concurrent tasks attempt to use the shared yfinance session
- **THEN** the adapter prevents simultaneous access to the shared session

#### Scenario: Async caller is cancelled

- **WHEN** the task awaiting a yfinance history operation is cancelled
- **THEN** cancellation propagates through the adapter
- **AND** it is not converted into a provider error

### Requirement: yfinance historical payloads are normalized internally

The yfinance adapter SHALL normalize historical provider payloads into repository-owned candle
models without exposing DataFrame objects, yfinance request options, or yfinance exceptions outside
`app/providers/`.

#### Scenario: Valid yfinance history rows are returned

- **WHEN** yfinance returns valid history rows for `SI=F`, `BZ=F`, `NG=F`, `KC=F`, `SB=F`,
  `ZW=F`, `ZC=F`, `^GSPC`, `^NDX`, or `^DJI`
- **THEN** the adapter returns normalized `Candle` values keyed by the gateway symbol metadata
- **AND** each normalized candle uses `Decimal` OHLCV values and UTC datetimes

#### Scenario: yfinance history response is invalid or incomplete

- **WHEN** a yfinance history response is missing required time or OHLC fields, contains an
  invalid decimal, duplicates a timestamp, or reports a provider failure
- **THEN** the adapter raises the provider-unavailable boundary
- **AND** it does not expose raw yfinance details outside the adapter

## MODIFIED Requirements

### Requirement: yfinance market-data routing remains out of scope

This change SHALL NOT implement or wire yfinance WebSocket market-data routing. Latest quote and
historical candle routing may use yfinance only through repository-owned provider adapters.

#### Scenario: Public market-data routes are used after yfinance candle enablement

- **WHEN** enabled `YFINANCE` registry rows exist
- **THEN** public quote and candle routes may make yfinance provider calls through their provider
  routers
- **AND** public WebSocket routes make no yfinance provider calls
- **AND** existing Binance and Twelve Data market-data behavior remains unchanged

#### Scenario: Application starts after yfinance candle enablement

- **WHEN** the gateway application starts after this change
- **THEN** no yfinance client, session, WebSocket, or background task is opened during startup
