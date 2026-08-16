# Provider SDK Integration Specification

## Purpose

Define how official provider SDKs are isolated behind gateway-owned adapters while preserving
async service contracts and stable normalized models.
## Requirements
### Requirement: Binance Spot integration uses the official SDK

The gateway SHALL use the locked official `binance-sdk-spot` package for Binance Spot REST
operations and SHALL keep the SDK behind the repository-owned provider adapter boundary.

#### Scenario: Latest quotes require Binance data

- **WHEN** the quote service requests uncached Binance provider symbols
- **THEN** the Binance adapter invokes the official SDK `ticker_price` operation
- **AND** no direct HTTP request implementation is used

#### Scenario: SDK types are inspected outside the provider package

- **WHEN** domain, service, cache, and API modules are analyzed
- **THEN** they contain no imports of Binance SDK models, clients, configurations, or exceptions

### Requirement: Synchronous SDK work does not block the event loop

The gateway MUST execute synchronous Binance Spot REST SDK operations outside the ASGI event loop
and SHALL serialize access to the shared SDK REST client.

#### Scenario: SDK quote operation is slow

- **WHEN** the synchronous SDK quote operation is waiting for network I/O
- **THEN** unrelated async gateway work can continue on the event loop

#### Scenario: Concurrent refreshes reach the adapter

- **WHEN** concurrent tasks attempt to use the shared SDK REST client
- **THEN** the adapter prevents simultaneous access to its shared SDK session

### Requirement: SDK configuration preserves provider policy

The gateway SHALL configure the Binance Spot SDK from typed deployment settings, converting the
provider timeout to SDK milliseconds and disabling SDK retries.

#### Scenario: Provider client is constructed

- **WHEN** the Binance SDK REST client is created
- **THEN** its base path equals `BINANCE_REST_BASE_URL`
- **AND** its timeout represents `PROVIDER_HTTP_TIMEOUT_SECONDS` in milliseconds
- **AND** its retries value is `0`
- **AND** no API key or secret is required for latest quotes

### Requirement: SDK responses are normalized into gateway models

The Binance adapter SHALL convert SDK ticker-price response models into
`ProviderQuoteBatch` and SHALL preserve the existing decimal and symbol validation rules.

#### Scenario: SDK returns valid requested prices

- **WHEN** the SDK returns unique entries with finite positive prices for requested symbols
- **THEN** the adapter returns those prices as `Decimal` values keyed by provider symbol

#### Scenario: SDK response contains invalid, duplicate, unexpected, or missing entries

- **WHEN** an SDK response violates a provider payload validation rule
- **THEN** the adapter marks each affected requested symbol unavailable
- **AND** it does not expose the SDK response model outside the adapter

### Requirement: SDK failures remain sanitized

The gateway SHALL translate documented Binance SDK errors, response conversion failures, and
unexpected SDK failures into the existing provider-unavailable boundary without exposing SDK
details.

#### Scenario: SDK raises a documented Binance error

- **WHEN** the SDK raises a network, rate-limit, client, server, or other documented SDK error
- **THEN** the adapter raises `ProviderUnavailableError`
- **AND** the external quote error remains `PROVIDER_UNAVAILABLE`

#### Scenario: Async caller is cancelled

- **WHEN** the task awaiting the SDK operation is cancelled
- **THEN** cancellation propagates through the adapter
- **AND** it is not converted into a provider error

### Requirement: Superseded direct transport is removed

The migration MUST remove production code and tests whose only purpose was direct HTTPX Binance
transport while retaining HTTPX solely where required for application HTTP tests.

#### Scenario: Migration is complete

- **WHEN** the repository is searched for production Binance HTTPX integration
- **THEN** there is no HTTPX application lifespan client or provider HTTP dependency
- **AND** there is no raw Binance URL construction, query JSON encoding, or HTTPX provider error
  handling
- **AND** provider tests use fake SDK boundaries instead of HTTPX `MockTransport`

### Requirement: Latest quote behavior is preserved

The SDK migration MUST NOT change the existing latest-quotes HTTP, registry, cache, freshness, or
per-symbol error requirements.

#### Scenario: Existing quote regression suite runs after migration

- **WHEN** the SDK-backed adapter replaces the direct HTTP implementation
- **THEN** existing `/v1/quotes` contract tests continue to pass without response changes
- **AND** no database migration is introduced

### Requirement: Twelve Data Forex integration uses the official SDK

The gateway SHALL use the official Twelve Data Python SDK for the Forex provider foundation and
SHALL keep the SDK behind repository-owned provider adapter boundaries.

#### Scenario: Forex provider dependency is configured

- **WHEN** project dependencies are installed for the gateway
- **THEN** the official `twelvedata` package is available to provider adapter code
- **AND** no Twelve Data SDK type is required by domain, service, cache, database, or API modules

#### Scenario: SDK types are inspected outside the provider package

- **WHEN** domain, service, cache, database, and API modules are analyzed
- **THEN** they contain no imports of Twelve Data SDK clients, request builders, response objects,
  or exceptions

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
### Requirement: Twelve Data REST work does not block the event loop

The gateway MUST execute synchronous Twelve Data SDK REST operations outside the ASGI event loop
and SHALL serialize access to any shared Twelve Data SDK client used by the adapter.

#### Scenario: SDK price or time-series operation is slow

- **WHEN** a synchronous Twelve Data SDK REST operation waits for network I/O
- **THEN** unrelated async gateway work can continue on the event loop

#### Scenario: Concurrent calls reach the adapter

- **WHEN** concurrent tasks attempt to use the shared Twelve Data SDK client
- **THEN** the adapter prevents simultaneous access to the shared SDK session

### Requirement: Twelve Data Forex payloads are normalized internally

The Twelve Data adapter foundation SHALL normalize supported Twelve Data provider payloads into
repository-owned domain-compatible primitives without exposing SDK response structures outside
`app/providers/`.

#### Scenario: Latest Twelve Data prices are requested through the adapter

- **WHEN** the adapter receives provider symbols for `BTC/USD`, `ETH/USD`, `EUR/USD`, `GBP/USD`,
  `USD/JPY`, `AUD/USD`, `XAU/USD`, `AAPL`, `TSLA`, `NVDA`, or `MSFT`
- **THEN** it can request Twelve Data latest prices for those provider symbols
- **AND** it returns finite positive prices as `Decimal` values keyed by provider symbol

#### Scenario: Twelve Data time-series candles are requested through the adapter

- **WHEN** the adapter receives a supported gateway timeframe for a supported Twelve Data symbol
- **THEN** it maps the timeframe to the corresponding Twelve Data interval
- **AND** it can normalize returned OHLCV rows into internal candle-compatible values

#### Scenario: SDK response is invalid or incomplete

- **WHEN** a Twelve Data response is missing required price, time, or OHLC fields, contains an
  invalid decimal, or indicates a provider error
- **THEN** the adapter reports the affected provider symbol as unavailable or raises the
  provider-unavailable boundary
- **AND** it does not expose raw provider error details outside the adapter
### Requirement: Twelve Data WebSocket remains out of scope

This change SHALL NOT implement or wire Twelve Data WebSocket streaming.

#### Scenario: Gateway stream provider is constructed

- **WHEN** the application stream manager is initialized after this change
- **THEN** it continues to use the existing Binance-backed stream provider behavior
- **AND** no Twelve Data WebSocket client is opened by application startup or downstream
  subscriptions

### Requirement: Twelve Data adapter supports validated commodity and ETF instruments

The gateway SHALL use the official Twelve Data SDK behind a repository-owned adapter for `WTI`,
`SPY`, and `QQQ`.

#### Scenario: Validated instrument is requested
- **WHEN** the adapter receives `WTI`, `SPY`, or `QQQ`
- **THEN** it invokes the SDK with the matching provider symbol

#### Scenario: Instrument is outside the allowlist
- **WHEN** an unsupported Twelve Data symbol is requested
- **THEN** no provider request is made for that symbol

### Requirement: Twelve Data adapter terminology is asset-neutral

The Twelve Data adapter boundary SHALL use asset-neutral runtime names.

#### Scenario: Application providers are wired
- **WHEN** REST and WebSocket providers are built for `TWELVE_DATA`
- **THEN** their types and factories do not imply Forex-only support

### Requirement: Twelve Data volume normalization is asset-aware

The adapter SHALL preserve valid supplied volume and use decimal zero for absent or null volume.

#### Scenario: ETF candle includes volume
- **WHEN** SPY or QQQ supplies valid volume
- **THEN** the exact decimal volume is preserved

#### Scenario: WTI candle omits volume
- **WHEN** WTI omits volume or returns null
- **THEN** exact decimal zero is used

#### Scenario: Supplied volume is malformed
- **WHEN** volume is malformed, negative, or non-finite
- **THEN** the provider payload is rejected

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

### Requirement: yfinance market data uses repository-owned adapters

The gateway SHALL route enabled `YFINANCE` symbols through repository-owned yfinance adapters for
latest quotes, historical candles, and WebSocket market data while preserving provider-agnostic
domain and public contracts.

#### Scenario: Public market-data routes use YFINANCE mappings

- **WHEN** an enabled YFINANCE registry row is requested through quote, candle, or WebSocket routes
- **THEN** the gateway routes the persisted provider symbol to the matching yfinance adapter
- **AND** existing Binance and Twelve Data behavior remains unchanged
- **AND** no automatic fallback or provider-symbol remapping occurs

#### Scenario: Application starts after YFINANCE stream integration

- **WHEN** the gateway application starts without active downstream YFINANCE stream interests
- **THEN** no yfinance network request, WebSocket connection, subscription, or background task is
  opened
- **AND** yfinance provider state is initialized lazily when the corresponding operation is needed
### Requirement: yfinance latest quotes use the repository-owned adapter

The gateway SHALL obtain yfinance latest prices through a repository-owned provider adapter using
the locked yfinance package and SHALL keep all yfinance types, sessions, payloads, and exceptions
inside `app/providers/`.

#### Scenario: Supported yfinance quote is requested

- **WHEN** the adapter receives one of `AAPL`, `AUDUSD=X`, `BZ=F`, `BTC-USD`, `KC=F`, `ZC=F`,
  `^DJI`, `ETH-USD`, `EURUSD=X`, `GBPUSD=X`, `MSFT`, `NG=F`, `^NDX`, `NVDA`, `QQQ`, `^GSPC`,
  `SPY`, `SB=F`, `TSLA`, `JPY=X`, `ZW=F`, `CL=F`, or `SI=F`
- **THEN** it calls `Ticker.get_info()` for that provider symbol
- **AND** it uses `regularMarketPrice` as the provider price candidate

#### Scenario: Provider symbol is outside the yfinance allowlist

- **WHEN** the adapter receives a provider symbol outside the 23 approved mappings
- **THEN** it marks that symbol unavailable
- **AND** it makes no yfinance request for that symbol

#### Scenario: yfinance boundary is inspected

- **WHEN** production modules outside `app/providers/` are analyzed
- **THEN** they contain no imports of yfinance modules, clients, sessions, payload models, or
  exceptions

### Requirement: Approved yfinance symbols are shared across market-data adapters

The gateway MUST apply the same 23-symbol yfinance allowlist to latest-quote, historical-candle,
and WebSocket stream operations.

#### Scenario: Approved mapping is routed through any market-data path

- **WHEN** an approved yfinance mapping is active and requested through quote, candle, or stream
- **THEN** the matching yfinance adapter accepts its persisted provider symbol
- **AND** no adapter performs provider-symbol remapping or cross-provider fallback

#### Scenario: Unapproved mapping is requested through any market-data path

- **WHEN** a yfinance provider symbol outside the approved set reaches quote, candle, or stream
- **THEN** the matching adapter rejects it through the sanitized provider-unavailable boundary
- **AND** it makes no upstream request or subscription for that symbol

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
`app/providers/`. It SHALL preserve strict batch validation for structural and numeric failures
while supporting row-level quarantine for an isolated OHLC envelope violation when other valid rows
remain.

#### Scenario: Valid yfinance history rows are returned

- **WHEN** yfinance returns valid history rows for `SI=F`, `BZ=F`, `NG=F`, `KC=F`, `SB=F`,
  `ZW=F`, `ZC=F`, `^GSPC`, `^NDX`, or `^DJI`
- **THEN** the adapter returns normalized `Candle` values keyed by the gateway symbol metadata
- **AND** each normalized candle uses `Decimal` OHLCV values and UTC datetimes

#### Scenario: Isolated OHLC envelope failure is quarantined

- **WHEN** a non-empty yfinance history payload contains a row whose `High` or `Low` is inconsistent
  with its `Open` or `Close`
- **AND** at least one other eligible row has valid required fields and values
- **THEN** the adapter returns the valid normalized candles
- **AND** it excludes the inconsistent row without changing its values
- **AND** it does not retry or select another provider

#### Scenario: Yfinance history response is batch-fatal or incomplete

- **WHEN** a yfinance history response is missing required time or OHLC fields,
  contains an invalid decimal, a non-finite value, a duplicate timestamp, negative
  volume, or leaves no valid row after OHLC-envelope quarantine
- **THEN** the adapter raises the provider-unavailable boundary
- **AND** it does not expose raw yfinance details outside the adapter

### Requirement: yfinance asynchronous WebSocket details remain provider-local

The gateway SHALL isolate yfinance asynchronous WebSocket clients, decoded payloads, configuration,
tasks, and exceptions inside `app/providers/`.

#### Scenario: Production boundaries are inspected

- **WHEN** domain, service, cache, database, and API modules are analyzed
- **THEN** they contain no imports of yfinance WebSocket clients, pricing payload models, or
  exceptions
- **AND** they interact with the adapter only through repository-owned stream models and protocols

### Requirement: yfinance stream operations use public asynchronous SDK methods

The gateway SHALL use the locked yfinance package's public `AsyncWebSocket` operations for
connection, subscription, listening, unsubscribe, and close behavior.

#### Scenario: YFINANCE provider symbol is subscribed

- **WHEN** the adapter opens an approved YFINANCE provider-symbol interest
- **THEN** it uses `AsyncWebSocket.subscribe` with the persisted provider symbol
- **AND** consumes decoded messages through `AsyncWebSocket.listen`

#### Scenario: YFINANCE provider symbol is released

- **WHEN** the final reference for a provider symbol is removed
- **THEN** the adapter uses `AsyncWebSocket.unsubscribe` for that provider symbol

#### Scenario: Stream adapter is closed

- **WHEN** the adapter has no remaining interests or application shutdown begins
- **THEN** it uses `AsyncWebSocket.close`
- **AND** cancels and awaits adapter-owned tasks

### Requirement: yfinance WebSocket failures remain sanitized

The gateway SHALL translate yfinance connection, subscription, listener, unsubscribe, decode, and
close failures into existing provider lifecycle behavior without exposing SDK details publicly.

#### Scenario: Initial connection or subscription fails

- **WHEN** yfinance cannot establish or subscribe the first required provider-symbol interest
- **THEN** the adapter raises `ProviderUnavailableError`
- **AND** the downstream connection receives only the existing sanitized provider-unavailable
  behavior

#### Scenario: Active listener terminates unexpectedly

- **WHEN** the yfinance listener fails after interests are registered
- **THEN** the adapter emits a repository-owned reconnecting signal for affected interests
- **AND** no SDK exception text, URL, or raw payload reaches downstream clients

#### Scenario: Adapter task is cancelled

- **WHEN** application shutdown or interest cleanup cancels adapter-owned asynchronous work
- **THEN** cancellation is treated as lifecycle control
- **AND** it is not converted into a provider error

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

### Requirement: Twelve Data REST rotates configured API keys
The Twelve Data REST adapter SHALL choose among configured healthy Twelve Data API keys inside the
provider boundary and SHALL keep SDK clients, keys, and provider exceptions out of domain, service,
cache, database, and API modules.

#### Scenario: REST request uses the next healthy key
- **WHEN** a Twelve Data REST quote or candle operation requires live provider data
- **THEN** the adapter selects a healthy configured Twelve Data key for the SDK client
- **AND** the public response shape remains unchanged

#### Scenario: Selected key is temporarily unavailable
- **WHEN** a Twelve Data REST operation fails with a key-related provider failure such as quota,
  rate-limit, or authentication exhaustion
- **THEN** the adapter marks that key unavailable for a short process-local cooldown
- **AND** it retries the same operation at most once with another healthy configured key

#### Scenario: No alternate key is healthy
- **WHEN** a Twelve Data REST operation requires live provider data and no configured key is
  currently usable
- **THEN** the adapter raises the sanitized provider-unavailable boundary
- **AND** it does not expose any API key, raw provider payload, SDK exception, or credential detail

#### Scenario: Provider reports no candle data
- **WHEN** Twelve Data returns the recognized no-data time-series condition for a valid candle range
- **THEN** the adapter preserves the existing successful empty-candle behavior
- **AND** it does not cool down the selected key

### Requirement: Twelve Data WebSocket key selection occurs at connection boundaries
The Twelve Data stream adapter SHALL choose a configured Twelve Data API key when opening a
WebSocket connection and MUST NOT rotate keys on a live connected WebSocket subscription.

#### Scenario: Stream connection is opened
- **WHEN** the first active Twelve Data stream interest requires a WebSocket connection
- **THEN** the adapter selects one configured healthy Twelve Data key to construct the SDK
  WebSocket client

#### Scenario: Stream connection remains active
- **WHEN** a Twelve Data WebSocket connection is already active
- **THEN** new subscriptions reuse the active connection
- **AND** no live key rotation occurs

#### Scenario: Stream reconnects after failure
- **WHEN** the Twelve Data stream adapter must create a new WebSocket connection after disconnect
  or provider failure
- **THEN** it may select another healthy configured Twelve Data key at that reconnect boundary

### Requirement: Twelve Data adapter supports crypto instruments

The gateway SHALL use the existing Twelve Data REST and stream adapter boundaries for `BTC/USD`
and `ETH/USD` when those canonical symbols are mapped to `TWELVE_DATA`.

#### Scenario: Valid crypto instrument is requested
- **WHEN** the adapter receives `BTC/USD` or `ETH/USD`
- **THEN** it invokes the SDK with the matching provider symbol

#### Scenario: Crypto instrument is outside the allowlist
- **WHEN** an unsupported Twelve Data crypto symbol is requested
- **THEN** no provider request is made for that symbol
