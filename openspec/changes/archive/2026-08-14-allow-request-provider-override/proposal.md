## Why

Clients can discover only each asset's default provider and every market-data request is forced through that active mapping, even when another verified Provider Mapping already exists. The gateway needs an explicit, asset-scoped Provider Override so consumers can request a supported upstream source without changing registry defaults or risking cross-provider data reuse.

## What Changes

- Add an optional, request-wide, case-sensitive `provider` query parameter to latest quote, historical candle, historical price, and WebSocket stream requests; omitting it preserves Default Provider behavior.
- Validate a Provider Override independently against each asset's configured Provider Mappings, regardless of default state: quotes retain per-symbol partial outcomes, while single-asset HTTP requests and WebSocket subscriptions reject unsupported selections without mutating registry state or falling back.
- Preserve latest-quote partial outcomes, reject unsupported providers for single-asset HTTP requests, and reject invalid WebSocket subscriptions before upstream access with stable `INVALID_PROVIDER` and `UNSUPPORTED_PROVIDER` errors.
- Extend `GET /v1/symbols` with deterministic `providerMappings` discovery while retaining the existing default `provider` and `providerSymbol` fields.
- Isolate quote cache entries, forming candle cache entries, persisted candle reads, and WebSocket interests by the resolved Provider Selection while permitting Default Provider and override requests to share state when they resolve to the same mapping.
- Keep market-data responses provider-agnostic and keep a Provider Selection fixed for the lifetime of an HTTP request or WebSocket subscription.
- Preserve the selected Provider Mapping across Historical Price Resolution, including provider-specific timeframe fallback supplied by the concurrent historical-price change, without look-ahead or cross-provider fallback.
- Require every exposed Provider Mapping to be verified across the complete market-data surface before release; incomplete mappings must be fixed or removed rather than hidden behind a second allowlist.

## Capabilities

### New Capabilities

- `request-provider-selection`: Define Provider Override parsing, asset-scoped mapping eligibility, immutable selection, error precedence, provider-aware data identity, and operational availability behavior shared by market-data APIs.

### Modified Capabilities

- `supported-symbol-registry`: Expose every configured Provider Mapping for each enabled asset while preserving the current default-provider fields and fail-closed registry behavior.
- `latest-quotes`: Accept a request-wide Provider Override, preserve partial outcomes, and isolate quote caching by Provider Selection.
- `historical-candles`: Accept a Provider Override and restrict persistence reuse and provider fills to the selected provider-owned candle series.
- `historical-price`: Accept a Provider Override and preserve that selection across the internal Historical Price Resolution policy without exposing provider or timeframe.
- `market-data-websocket-stream`: Accept a Provider Override, validate the complete subscription, and isolate shared upstream interests and cache updates by Provider Selection.

## Impact

- Affects public query validation and OpenAPI contracts for `/v1/quotes`, `/v1/candles`, `/v1/historical-price`, and `/v1/stream`, plus the response schema for `/v1/symbols`.
- Affects symbol resolution, quote and candle services, in-memory caches, provider routers, stream interest identity, structured observability, and PostgreSQL repository queries.
- Requires API-boundary acceptance tests with fake upstream adapters, focused PostgreSQL mapping tests, and isolation tests for cache, candle history, and simultaneous streams.
- Requires verification of all existing inactive alternatives before release and coordination with the concurrent Historical Price Resolution change.
- Adds no provider adapter, dependency, provider administration API, automatic fallback, seed mapping, or database schema change.
