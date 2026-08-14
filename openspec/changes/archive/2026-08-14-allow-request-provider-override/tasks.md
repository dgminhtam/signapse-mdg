## 1. Provider Selection Foundation

- [x] 1.1 Add typed Provider Mapping and immutable Provider Selection domain values, including `DEFAULT` and `OVERRIDE` selection modes.
- [x] 1.2 Add sanitized `INVALID_PROVIDER` and `UNSUPPORTED_PROVIDER` gateway errors with the agreed HTTP and WebSocket mappings.
- [x] 1.3 Implement shared query parsing that distinguishes omitted, empty or whitespace-only, repeated, and exact case-sensitive `provider` values before registry access.
- [x] 1.4 Update the symbol repository to load every normalized mapping for enabled assets, identify exactly one Default Provider, and fail closed when that invariant is broken.
- [x] 1.5 Implement one asset-scoped resolver for default and explicit Provider Selections with request-shape, asset, then mapping validation precedence and no fallback.

## 2. Symbol Discovery

- [x] 2.1 Extend symbol domain and API DTOs with ordered `providerMappings` entries containing exactly `provider`, `providerSymbol`, and `isDefault`.
- [x] 2.2 Update `GET /v1/symbols` to retain default `provider` and `providerSymbol`, put the default mapping first, sort remaining mappings by Provider Identifier, and expose no runtime health fields.
- [x] 2.3 Add PostgreSQL-backed API tests proving enabled assets expose all configured mappings and invalid no-default registry state fails closed.

## 3. Latest Quote Selection

- [x] 3.1 Pass resolved Provider Selections through quote grouping and provider routing while preserving request order and per-symbol partial outcomes.
- [x] 3.2 Key quote cache entries by canonical symbol, Provider Identifier, and provider symbol, and restrict TTL and stale fallback reuse to the same selection.
- [x] 3.3 Extend `GET /v1/quotes` with request-wide Provider Override handling, per-symbol `UNSUPPORTED_PROVIDER`, and provider-agnostic success and error payload contracts.
- [x] 3.4 Add public-boundary quote tests with real routes, services, router, cache, PostgreSQL repositories, and fake upstream adapters for default, override, mixed support, all unsupported, malformed provider, isolation, and operational failure cases.

## 4. Candle and Historical Price Selection

- [x] 4.1 Pass one resolved Provider Selection through candle persistence reads, missing-window fills, provider routing, normalization, and writes without mixing or relabeling provider-owned rows.
- [x] 4.2 Key forming candle cache entries by canonical symbol, Provider Identifier, provider symbol, and timeframe.
- [x] 4.3 Extend `GET /v1/candles` with Provider Override parsing and the agreed `400 INVALID_PROVIDER`, `400 UNSUPPORTED_PROVIDER`, and `503 PROVIDER_UNAVAILABLE` behavior.
- [x] 4.4 Reconcile `HistoricalPriceService` with the concurrent provider-specific timeframe policy so every attempted timeframe receives the same immutable Provider Selection and only candles with `close_time <= at` are eligible.
- [x] 4.5 Extend `GET /v1/historical-price` with Provider Override while keeping the exact `symbol`, `price`, and `pricedAt` response and mapping no-data exhaustion to `PRICE_NOT_FOUND` without masking operational failures.
- [x] 4.6 Add public-boundary candle and historical-price tests with real routes, services, routers, caches, PostgreSQL repositories, and fake upstream adapters for selection, provider-owned persistence, no look-ahead, coarser-timeframe retry, no cross-provider fallback, and sanitized failures.

## 5. WebSocket Selection and Identity

- [x] 5.1 Include Provider Identifier and provider symbol in quote and candle Stream Interest identity, with channel and timeframe where applicable.
- [x] 5.2 Extend `WS /v1/stream` validation with one request-wide Provider Override and all-or-nothing `1008 INVALID_PROVIDER`, `1008 UNSUPPORTED_PROVIDER`, and `1011 DATABASE_UNAVAILABLE` closure behavior before provider access.
- [x] 5.3 Pass immutable Provider Selections through stream manager and provider router registration, reference counting, fanout, cleanup, and reconnect behavior.
- [x] 5.4 Preserve sharing only for clients selecting the same mapping and preserve active connections when a Default Provider changes.
- [x] 5.5 Map selected-adapter or upstream establishment failures to `1011 PROVIDER_UNAVAILABLE` without provider fallback.
- [x] 5.6 Add public-boundary WebSocket tests with real route, manager, router, caches, PostgreSQL repositories, and fake upstream adapters for default, override, whole-subscription rejection, simultaneous mapping isolation, sharing, default changes, and operational failure.

## 6. Observability and Verification

- [x] 6.1 Add sanitized structured logs containing canonical symbol, provider, provider symbol, and selection mode at selection and provider-routing boundaries.
- [x] 6.2 Add or update metrics using provider and selection mode without provider symbol as a label.
- [x] 6.3 Add focused repository tests for all-mapping loading, exact case-sensitive resolution, non-default eligibility, and no-default fail-closed behavior.
- [x] 6.4 Add focused cache and stream tests proving state for two mappings of the same canonical symbol cannot cross selection boundaries.
- [x] 6.5 Add a focused Historical Price Resolution integration test proving timeframe changes preserve Provider Selection and operational failures stop resolution.

## 7. Release Gate and Documentation

- [x] 7.1 Smoke-test every existing Provider Mapping across latest quote, all public candle timeframes, Historical Price Resolution, and WebSocket quote and candle delivery; fix or remove incomplete mappings before release.
- [x] 7.2 Update `docs/provider-support-verification.md` with full-surface evidence for default and non-default mappings and confirm selection is derived only from PostgreSQL mappings.
- [x] 7.3 Update `docs/spec.md` and related system design documentation with Provider Override inputs, discovery output, validation precedence, errors, identity isolation, and historical-price concurrency boundary.
- [x] 7.4 Run `uv run pytest`, `uv run ruff check .`, and `uv run mypy app`, then record test and cross-change reconciliation evidence.
