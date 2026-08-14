## Context

The normalized registry already stores one or more Provider Mappings per canonical asset and marks exactly one as the Default Provider. Runtime repositories currently flatten only that active mapping into the symbol model, while quote, candle, historical-price, and stream services have no request-level provider selector. The public symbol API likewise exposes only the default mapping.

Provider ownership is already part of persisted candle identity, but process-local quote cache entries, forming candle cache entries, and stream interests are keyed only by canonical symbol and timeframe. Selecting a non-default mapping without changing those identities would allow one provider's data or subscription to satisfy another provider's request.

The concurrent Historical Price Resolution change will replace the current fixed `1m` lookup with a provider-specific timeframe policy. This change must pass one immutable Provider Selection through that policy but must not recreate or independently define its exact timeframe ladder.

## Goals / Non-Goals

**Goals:**

- Resolve either the Default Provider or one explicit request-wide Provider Override for every market-data operation.
- Distinguish malformed provider input, unknown or disabled assets, unsupported asset-provider combinations, and transient provider unavailability.
- Prevent cache, persistence, and subscription data from crossing Provider Mapping boundaries.
- Preserve existing response shapes and default behavior when `provider` is omitted.
- Expose deterministic Provider Mapping discovery for enabled assets.
- Keep the design compatible with provider-specific Historical Price Resolution without look-ahead or provider fallback.

**Non-Goals:**

- Automatic provider fallback, aggregation, priority, or health-based routing.
- Per-symbol provider choices within one request.
- Provider administration, default-switching, or provider-health APIs.
- Capability flags per Provider Mapping or partial-capability mappings.
- Provider adapter, dependency, database schema, or seed changes.
- Provider selection for candle backfill, economic calendar, crawl, or health operations.
- Definition of the concurrent Historical Price Resolution timeframe ladder.

## Decisions

### Resolve a request to one immutable Provider Selection per asset

The optional `provider` value is a case-sensitive Provider Identifier applied to every asset in the request. The registry layer will distinguish canonical asset metadata, its configured Provider Mappings, and the immutable Provider Selection passed to market-data services and adapters.

Every enabled asset must retain exactly one Default Provider. Resolution first enforces that registry invariant and preserves the existing fail-closed `DATABASE_UNAVAILABLE` behavior when the default is absent, even if a request names another configured mapping. When `provider` is absent, resolution selects the default mapping. When `provider` is present, resolution selects the matching mapping regardless of default state; a missing mapping is `UNSUPPORTED_PROVIDER` and never changes registry state. The selection is resolved once and remains fixed for the HTTP request or WebSocket connection.

Alternative considered: temporarily activate the requested mapping in PostgreSQL. Rejected because request routing must not mutate global defaults or race with other clients. Alternative considered: let each service query mappings independently. Rejected because it duplicates precedence and makes one operation vulnerable to mixed selections.

### Treat every configured mapping as full-surface support

Mapping existence is the only asset-scoped allowlist. Every mapping exposed by the registry must be verified for latest quote, public candle timeframes, Historical Price Resolution, and WebSocket quote/candle data. No second hard-coded selectable-provider list or capability flags will be added.

Alternative considered: add quote, candle, historical-price, and stream capability flags. Rejected because the agreed domain invariant is one mapping shared across the complete market-data surface, and flags would reintroduce route-specific states that the normalized registry deliberately removed.

### Parse provider input before registry or provider access

Routes will inspect all `provider` query values. An absent value means Default Provider; an empty or whitespace-only value and repeated values are request-level `INVALID_PROVIDER`. Any other value remains case-sensitive and is validated only against each asset's mappings. The gateway will not add a global provider-validity concept.

Request-shape validation precedes canonical asset validation, which precedes Provider Mapping validation. Thus an unknown or disabled asset remains `UNSUPPORTED_SYMBOL`; a valid asset lacking the requested mapping is `UNSUPPORTED_PROVIDER`. Quote requests retain per-symbol partial outcomes, while single-asset HTTP requests and WebSocket subscriptions retain their current request-level/all-or-nothing boundaries.

Alternative considered: normalize provider case or accept aliases. Rejected because Provider Identifiers are stable public values discoverable from the registry and must remain identical across selection, cache identity, logs, and metrics.

### Use Provider Selection as the data identity

Quote cache identity will include canonical symbol, Provider Identifier, and provider symbol. Forming candle cache and stream interest identity will include the same fields plus timeframe or channel as applicable. Default and override requests may share entries or upstream subscriptions only when they resolve to the same mapping.

Persisted candle reads will continue filtering by provider and provider symbol, and writes will retain their existing provider-owned identity. Provider switches or overrides do not relabel, merge, or delete another mapping's candle history.

Alternative considered: keep canonical-symbol cache keys and invalidate them when an override arrives. Rejected because concurrent default and override requests or streams must coexist and invalidation cannot provide isolation.

### Keep public market-data payloads provider-agnostic

Quote, candle, historical-price, WebSocket data, and status payloads retain their exact current fields. Clients know an explicit Provider Override from their request and can discover the Default Provider from the symbol registry. No provider response field or header is added.

`GET /v1/symbols` retains the existing default `provider` and `providerSymbol` fields and adds `providerMappings`. Each mapping contains `provider`, `providerSymbol`, and `isDefault`; the default appears first and remaining mappings are ordered by Provider Identifier.

Alternative considered: echo the resolved provider on every response and event. Rejected because it breaks minimal provider-agnostic contracts and duplicates request or registry information.

### Preserve existing provider failure and freshness behavior within one selection

A configured mapping with a missing adapter, credential, upstream timeout, rate limit, transport failure, or invalid payload remains supported but operationally unavailable. Existing `PROVIDER_UNAVAILABLE`, quote partial-outcome, and WebSocket close behavior apply without fallback.

Quote TTL and stale fallback rules continue unchanged but may reuse only a cached quote belonging to the same Provider Selection. Exhaustion of valid Historical Price Resolution timeframes returns `PRICE_NOT_FOUND`; operational provider failures remain `PROVIDER_UNAVAILABLE` and are not hidden by trying another provider.

### Integrate with Historical Price Resolution through a selected-mapping seam

Historical price accepts the same optional Provider Override but exposes neither provider nor timeframe. It resolves one Provider Selection and passes it through every timeframe attempted by the provider-specific resolution policy. The selected candle must be complete at `at` so coarser timeframes cannot introduce look-ahead; `pricedAt` remains that candle's open time.

The exact timeframe ladder and retention thresholds belong to the concurrent Historical Price Resolution change. The shared seam is the immutable Provider Selection supplied to the resolver; final integration tests must prove the resolver never changes provider while changing timeframe.

Alternative considered: keep the fixed `1m` contract in this change and retrofit selection later. Rejected because that would couple Provider Override to an obsolete resolution interface and create avoidable rework when the concurrent change lands.

### Test at the public API boundary

Primary acceptance tests will drive real HTTP and WebSocket routes, services, routers, caches, and PostgreSQL repositories while replacing only upstream provider adapters. Focused repository tests will cover mapping resolution and provider-owned candle history; focused cache and stream tests will cover simultaneous selections for one canonical symbol. No live upstream call is part of the automated suite.

### Keep provider selection observable but internal

Structured logs will include canonical symbol, provider, provider symbol, and `DEFAULT` or `OVERRIDE` selection mode. Metrics may use provider and selection mode but will not use provider symbol as a label. Public errors remain sanitized.

## Risks / Trade-offs

- [Existing alternative mappings have not been verified across every surface] → Make full-surface verification a release gate; fix or remove any incomplete mapping before exposing the feature.
- [Provider-aware keys increase cache and upstream subscription cardinality] → Preserve existing limits and sharing for requests resolving to the same mapping; observe counts by provider and selection mode.
- [A Default Provider changes during a long-lived stream] → Keep the stream's selection snapshot stable and apply the new default only to new connections.
- [The concurrent historical-price change modifies the same request/service seam] → Keep the interface selection-focused, reconcile the two changes before final tests, and do not duplicate its timeframe ladder.
- [Additional registry mappings make `/v1/symbols` responses larger] → The catalog is small, deterministic, and bounded by configured mappings; avoid dynamic health fields.
- [Direct SQL can create a mapping the application cannot actually serve] → Treat mapping insertion as a verified configuration release step and keep the provider-availability boundary sanitized at runtime.

## Migration Plan

1. Verify every existing Provider Mapping across the complete market-data surface and update provider-support evidence; fix or remove failures.
2. Deploy provider-aware domain identity, registry resolution, caches, and stream interests before clients begin sending overrides. Process-local caches start empty on restart, so no cache migration is required.
3. Deploy the additive query parameters and symbol discovery response together with contract tests proving omitted-provider backward compatibility.
4. Reconcile the selected-mapping seam with the concurrent Historical Price Resolution change and run cross-change historical-price tests.
5. Enable client use of Provider Override and monitor provider/selection metrics.

Rollback deploys the previous application version. Existing clients that omit `provider` remain compatible, no database rollback is needed, and provider-owned candle rows remain valid.

## Open Questions

None within this change. The exact Historical Price Resolution timeframe ladder and retention thresholds remain an explicit dependency owned by the concurrent change.
