## ADDED Requirements

### Requirement: yfinance latest quotes use the repository-owned adapter

The gateway SHALL obtain yfinance latest prices through a repository-owned provider adapter using
the locked yfinance package and SHALL keep all yfinance types, sessions, payloads, and exceptions
inside `app/providers/`.

#### Scenario: Supported yfinance quote is requested

- **WHEN** the adapter receives one of `SI=F`, `BZ=F`, `NG=F`, `KC=F`, `SB=F`, `ZW=F`, `ZC=F`,
  `^GSPC`, `^NDX`, or `^DJI`
- **THEN** it calls `Ticker.get_info()` for that provider symbol
- **AND** it uses `regularMarketPrice` as the provider price candidate

#### Scenario: Provider symbol is outside the yfinance allowlist

- **WHEN** the adapter receives a provider symbol outside the ten approved mappings
- **THEN** it marks that symbol unavailable
- **AND** it makes no yfinance request for that symbol

#### Scenario: yfinance boundary is inspected

- **WHEN** production modules outside `app/providers/` are analyzed
- **THEN** they contain no imports of yfinance modules, clients, sessions, payload models, or
  exceptions

### Requirement: yfinance synchronous work does not block the event loop

The gateway MUST execute synchronous yfinance quote work outside the ASGI event loop and SHALL
serialize access to shared yfinance session, cookie, crumb, and singleton state.

#### Scenario: yfinance quote operation is slow

- **WHEN** a synchronous `get_info()` operation waits for Yahoo network I/O
- **THEN** unrelated async gateway work can continue on the event loop

#### Scenario: Concurrent yfinance refreshes reach the adapter

- **WHEN** concurrent tasks attempt to refresh yfinance quotes
- **THEN** the adapter prevents simultaneous access to its shared yfinance state
- **AND** each supported symbol is fetched at most once within its serialized refresh batch

#### Scenario: Async caller is cancelled

- **WHEN** the task awaiting yfinance quote work is cancelled
- **THEN** cancellation propagates through the adapter
- **AND** it is not converted into a provider error

### Requirement: yfinance requests use the configured provider timeout

The gateway SHALL apply `PROVIDER_HTTP_TIMEOUT_SECONDS` to each underlying yfinance HTTP request
through a yfinance-compatible shared session and SHALL require no Yahoo credential.

#### Scenario: yfinance session is constructed

- **WHEN** the quote adapter creates its shared provider session
- **THEN** each session request uses a timeout no greater than
  `PROVIDER_HTTP_TIMEOUT_SECONDS`
- **AND** no API key, secret, or new provider base URL is required

#### Scenario: Yahoo request exceeds the timeout

- **WHEN** an underlying yfinance HTTP request exceeds the configured provider timeout
- **THEN** the affected provider symbol is unavailable
- **AND** internal session, URL, cookie, and exception details are not exposed publicly

### Requirement: yfinance quote payloads are normalized per symbol

The yfinance adapter SHALL return finite positive `Decimal` prices keyed by provider symbol and
SHALL preserve successful symbols when another symbol fails validation or retrieval.

#### Scenario: regular market price is valid

- **WHEN** `regularMarketPrice` is a finite numeric value greater than zero
- **THEN** the adapter converts its string representation to `Decimal`
- **AND** returns it under the matching requested provider symbol

#### Scenario: regular market price is invalid

- **WHEN** `regularMarketPrice` is absent, boolean, non-numeric, non-finite, zero, or negative
- **THEN** the adapter marks that provider symbol unavailable
- **AND** it does not return a price for that symbol

#### Scenario: one ticker operation fails

- **WHEN** one requested ticker raises a yfinance, HTTP, timeout, rate-limit, payload, or unexpected
  exception
- **THEN** the adapter marks that ticker unavailable
- **AND** continues processing the remaining requested provider symbols

#### Scenario: shared provider setup fails

- **WHEN** the shared yfinance session or batch cannot be initialized or used
- **THEN** the adapter raises `ProviderUnavailableError`
- **AND** the external quote behavior remains sanitized

## MODIFIED Requirements

### Requirement: yfinance market-data routing remains out of scope

The gateway SHALL route enabled `YFINANCE` symbols through the yfinance adapter for latest quote
requests only and SHALL NOT implement or wire yfinance historical candle or WebSocket
market-data routing.

#### Scenario: Public quote route is used after yfinance quote integration

- **WHEN** an enabled `YFINANCE` registry row is requested through `GET /v1/quotes`
- **THEN** the gateway routes the persisted provider symbol to the yfinance quote adapter
- **AND** existing Binance and Twelve Data quote behavior remains unchanged

#### Scenario: Candle or stream route targets yfinance

- **WHEN** an enabled `YFINANCE` symbol is requested through historical candle or WebSocket routes
- **THEN** no yfinance candle or WebSocket provider call is made
- **AND** the existing provider-unavailable behavior is preserved

#### Scenario: Application starts after quote integration

- **WHEN** the gateway application starts after this change
- **THEN** no yfinance network request, WebSocket, or background polling task is opened during
  startup
- **AND** the quote adapter initializes provider state lazily when quote data is required
