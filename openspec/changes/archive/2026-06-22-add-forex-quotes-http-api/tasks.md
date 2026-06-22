## 1. Quote Provider Routing

- [x] 1.1 Introduce a quote provider routing boundary that can dispatch pending `SupportedSymbol` records by persisted `provider`.
- [x] 1.2 Keep existing Binance adapter behavior for `BINANCE_SPOT` provider groups, including batched provider-symbol refresh.
- [x] 1.3 Route `TWELVE_DATA` provider groups to the existing Twelve Data Forex latest-price adapter.
- [x] 1.4 Preserve canonical-symbol cache keys and existing quote cache TTL/freshness fallback semantics.
- [x] 1.5 Isolate provider group failures so one failed provider group only affects symbols in that group.
- [x] 1.6 Treat unsupported provider names or missing unusable provider configuration as sanitized provider-unavailable results for affected symbols.

## 2. FastAPI Dependency Wiring

- [x] 2.1 Update quote route dependency construction to build both Binance and Twelve Data quote providers behind the router.
- [x] 2.2 Ensure missing `TWELVEDATA_API_KEY` does not fail application startup or crypto-only quote requests.
- [x] 2.3 Ensure Twelve Data SDK imports remain confined to `app/providers/`.
- [x] 2.4 Keep public quote response DTOs unchanged.

## 3. Tests

- [x] 3.1 Add quote service/provider-router tests for mixed `BINANCE_SPOT` and `TWELVE_DATA` success.
- [x] 3.2 Add tests proving Twelve Data provider failure does not block successful Binance quotes in the same request.
- [x] 3.3 Add tests proving missing Twelve Data configuration reports Forex symbols as `PROVIDER_UNAVAILABLE` while crypto can still succeed.
- [x] 3.4 Add route/dependency tests for Forex quote requests using fake providers without live Twelve Data calls.
- [x] 3.5 Update existing latest quote tests that assume Binance-only provider behavior.
- [x] 3.6 Confirm candle and WebSocket tests remain Binance-backed and do not instantiate Twelve Data streams.

## 4. Documentation and Specs

- [x] 4.1 Update `docs/spec.md` quote section to mention Forex quote support without adding quote fields.
- [x] 4.2 Update `docs/system-design.md` provider flow to describe quote provider routing for Binance crypto and Twelve Data Forex.
- [x] 4.3 Update environment/runbook notes for `TWELVEDATA_API_KEY` being required only for live Forex quote refreshes.

## 5. Verification

- [x] 5.1 Run `openspec validate add-forex-quotes-http-api --strict`.
- [x] 5.2 Run latest quote provider, service, route, and regression unit tests.
- [x] 5.3 Run relevant integration tests for registry-backed quote mappings when `TEST_DATABASE_URL` is available.
- [x] 5.4 Run `ruff` and `mypy` for touched application code.
