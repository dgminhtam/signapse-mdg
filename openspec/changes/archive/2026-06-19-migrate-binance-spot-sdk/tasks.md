## 1. Dependency and SDK Contract Inspection

- [x] 1.1 Add locked runtime dependency `binance-sdk-spot==9.2.0`, move `httpx==0.28.1` to the development group, and refresh `uv.lock`.
- [x] 1.2 Inspect the installed SDK `Spot`, `ConfigurationRestAPI`, `ticker_price`, `ApiResponse.data()`, generated ticker-price models, exception hierarchy, and typing metadata under Python 3.14.6.
- [x] 1.3 Record any necessary SDK typing workaround locally at the provider boundary; do not weaken project-wide strict mypy settings.

## 2. SDK-Backed Binance Adapter

- [x] 2.1 Add a narrow typed SDK REST protocol or callable boundary that can be replaced by a fake in tests.
- [x] 2.2 Add a Binance SDK client factory using `BINANCE_REST_BASE_URL`, timeout converted to milliseconds, `retries=0`, and no credentials.
- [x] 2.3 Replace direct HTTPX quote retrieval with SDK `ticker_price(symbols=...)` executed through `asyncio.to_thread`.
- [x] 2.4 Serialize shared SDK REST client access without changing the async `QuoteProvider` interface.
- [x] 2.5 Normalize SDK response models into `ProviderQuoteBatch`, preserving requested-symbol, duplicate, missing, finite-positive decimal, and unexpected-entry validation.
- [x] 2.6 Map documented SDK errors, response conversion failures, and unexpected SDK failures to `ProviderUnavailableError` while allowing task cancellation to propagate.

## 3. Application Wiring and Cleanup

- [x] 3.1 Replace the quote route's HTTP client dependency with SDK provider or SDK client dependency wiring that remains overridable in tests.
- [x] 3.2 Remove the FastAPI HTTPX lifespan client and restore a simple application lifecycle unless another production resource requires lifespan.
- [x] 3.3 Delete `app/core/http.py` and remove all production imports and state associated with it.
- [x] 3.4 Remove raw Binance URL construction, JSON query encoding, raw response decoding, HTTP status handling, and HTTPX exceptions from the provider adapter.
- [x] 3.5 Search production source to confirm HTTPX is no longer imported and no direct Binance REST fallback path remains.

## 4. Test Migration and Regression Coverage

- [x] 4.1 Rewrite Binance adapter tests around fake SDK response wrappers/models and documented SDK exceptions instead of HTTPX `MockTransport`.
- [x] 4.2 Add async tests proving slow SDK calls do not block the event loop and concurrent adapter calls are serialized.
- [x] 4.3 Add tests for SDK response conversion failures, unexpected exceptions, timeout/rate-limit errors, and cancellation propagation.
- [x] 4.4 Replace the PostgreSQL quote-mapping integration override with a fake SDK or provider boundary and remove provider-specific HTTPX fixtures.
- [x] 4.5 Run the existing quote service and route regression suites unchanged to prove API, cache, registry, freshness, ordering, and per-symbol errors are preserved.

## 5. Documentation and Verification

- [x] 5.1 Update `docs/tech-stack.md`, `docs/system-design.md`, `docs/spec.md`, `README.md`, and provider references to identify `binance-sdk-spot==9.2.0` as the runtime Binance integration.
- [x] 5.2 Remove documentation that describes HTTPX as the production Binance client while retaining it as an ASGI test dependency.
- [x] 5.3 Run Ruff format/check, strict mypy, the full pytest suite, and PostgreSQL integration tests when `TEST_DATABASE_URL` is available.
- [x] 5.4 Verify no Alembic revision was added and run live smoke tests for `/health`, `/v1/symbols`, and SDK-backed `/v1/quotes`.
- [x] 5.5 Run a final repository search confirming no obsolete HTTPX provider wiring, raw Binance request code, or SDK types outside `app/providers/` remain.
