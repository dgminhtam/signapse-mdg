## Context

`GET /v1/quotes` currently validates symbols through the PostgreSQL registry, but refreshes every
pending quote through a single Binance-backed `QuoteProvider`. The registry now contains both
crypto rows mapped to `BINANCE_SPOT` and Forex rows mapped to `TWELVE_DATA`, and the repository has
a Twelve Data Forex provider foundation capable of normalizing latest prices.

This change is the first public Forex market-data enablement step. It must preserve the existing
minimal quote response while making provider routing explicit enough to support mixed quote
requests such as `BTC/USD,EUR/USD`.

## Goals / Non-Goals

**Goals:**

- Allow `GET /v1/quotes` to return latest quotes for `EUR/USD`, `GBP/USD`, `USD/JPY`, and
  `AUD/USD` when those registry rows are enabled and Twelve Data is configured.
- Preserve existing Binance quote behavior for `BTC/USD` and `ETH/USD`.
- Preserve public quote response fields, request validation, quote cache semantics, and
  per-symbol partial outcomes.
- Route provider refreshes by the persisted provider mapping for each enabled symbol.
- Isolate failures by provider group so a Twelve Data failure does not break successful Binance
  crypto quotes in the same request.

**Non-Goals:**

- Do not add Forex candle support to `/v1/candles`.
- Do not add Forex or Twelve Data support to `/v1/stream`.
- Do not implement Twelve Data WebSocket streaming.
- Do not add provider fallback, aggregation, or cross-provider price reconciliation.
- Do not add new public quote fields.
- Do not add or modify database migrations.

## Decisions

### Add a quote provider router instead of branching in the route

The route dependency should construct a repository-owned provider routing object that implements
the existing `QuoteProvider` protocol. `QuoteService` can continue to depend on a quote provider,
while the provider router handles grouping by provider and dispatching to Binance or Twelve Data.

Alternative considered: branch in `routes_quotes.py` or add Forex-specific route dependencies.
That would couple API wiring to provider details and make mixed-symbol partial behavior harder to
test. Keeping dispatch behind the provider protocol preserves the service/adapter boundary.

### Pass supported symbol context to provider refreshes

The current `QuoteProvider.fetch_latest_prices(provider_symbols)` protocol only receives provider
symbols, which is not enough to route mixed provider requests. The service should refresh pending
`SupportedSymbol` records through a provider router that can inspect `provider` and
`provider_symbol`.

The narrowest approach is to introduce a repository-owned quote routing protocol or provider
router method that accepts `list[SupportedSymbol]` and returns provider-symbol keyed batches per
group, while retaining the concrete Binance and Twelve Data adapters behind their existing
provider-symbol-based methods.

Alternative considered: encode provider into the provider symbol string. That would leak registry
format assumptions into provider adapters and undermine replaceability.

### Keep cache keys canonical

The quote cache should continue to be keyed by canonical symbol. This keeps cache reuse and stream
quote updates compatible with the existing public contract and avoids provider-symbol collisions.

### Missing Twelve Data configuration is a Forex provider failure

If `TWELVEDATA_API_KEY` is absent or invalid, the application should still start and Binance crypto
quote requests should continue to work. Forex symbols that require Twelve Data should receive
`PROVIDER_UNAVAILABLE`, or use a fresh cached quote if one exists under the existing fallback rules.

Alternative considered: fail application startup when Twelve Data is not configured. That would
make an optional Forex capability break crypto-only deployments and local smoke tests.

### Do not route candles or streams by Forex yet

The existing candle and WebSocket routes are Binance-backed and have separate semantics for current
candle state, volume, stream freshness, and upstream lifecycle. This change intentionally leaves
them unchanged so quote enablement can be validated independently.

## Risks / Trade-offs

- **Twelve Data free-plan limits are tight** → Keep default tests mocked and do not require live
  provider smoke tests. Cache still limits repeated provider refreshes.
- **Twelve Data provider currently loops per symbol** → Accept for four initial Forex pairs; batch
  optimization can be considered later if limits or latency become painful.
- **Global refresh lock can serialize different provider groups** → Preserve current correctness
  first; finer-grained per-symbol/provider refresh locks can be a later performance improvement.
- **Registry can list Forex before API key is configured** → Treat missing key as symbol-level
  `PROVIDER_UNAVAILABLE`, keeping crypto behavior intact.
- **Spec still has Binance-focused historical wording** → This change updates latest-quote
  requirements to explicitly cover provider-routed refreshes while preserving Binance batch
  scenarios for crypto.

## Migration Plan

1. Deploy the existing Forex registry seed migration if not already applied.
2. Configure `TWELVEDATA_API_KEY` in environments that should serve live Forex quotes.
3. Deploy provider-routed quote code.
4. Validate:
   - `GET /v1/quotes?symbols=BTC/USD,ETH/USD`
   - `GET /v1/quotes?symbols=EUR/USD,GBP/USD,USD/JPY,AUD/USD`
   - mixed crypto/Forex request behavior.

Rollback:

- Revert the provider-routed quote code to Binance-only behavior.
- No database rollback is required; seeded Forex symbols can remain listed, but Forex quote
  requests would return provider unavailable or unsupported depending on the reverted behavior.

## Open Questions

- Should a later optimization batch Twelve Data price requests if the SDK supports stable batch
  `price` semantics for Forex under the selected plan?
- Should live Forex quote smoke tests be opt-in behind an environment flag and real Twelve Data
  key, or kept entirely manual for now?
