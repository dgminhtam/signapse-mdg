## 1. Adapter Contract Tests

- [x] 1.1 Add fake yfinance ticker and session boundaries that keep SDK types inside provider tests.
- [x] 1.2 Test the ten-symbol allowlist, unsupported-symbol short circuit, and
  `get_info().regularMarketPrice` selection.
- [x] 1.3 Test finite positive `Decimal(str(value))` normalization for integer, float, string, and
  decimal-compatible values.
- [x] 1.4 Test missing, boolean, malformed, non-finite, zero, and negative price handling.
- [x] 1.5 Test per-symbol exception isolation and batch-level `ProviderUnavailableError`
  sanitization.
- [x] 1.6 Test worker-thread execution, serialized shared-state access, cancellation propagation,
  and configured session timeout clamping.

## 2. yfinance Quote Adapter

- [x] 2.1 Add the provider-owned yfinance quote module, protocol boundaries, and approved provider
  symbol allowlist.
- [x] 2.2 Implement a lazily created yfinance-compatible shared session that clamps underlying HTTP
  requests to `PROVIDER_HTTP_TIMEOUT_SECONDS`.
- [x] 2.3 Implement serialized `asyncio.to_thread()` batch execution using
  `Ticker.get_info()["regularMarketPrice"]`.
- [x] 2.4 Normalize successful prices into `ProviderQuoteBatch` and preserve per-symbol partial
  failures without leaking provider details.

## 3. Quote Routing

- [x] 3.1 Add unit coverage proving `QuoteProviderRouter` dispatches `YFINANCE` symbols and isolates
  failures from Binance and Twelve Data groups.
- [x] 3.2 Add the cached yfinance quote-provider factory and register `YFINANCE` in quote dependency
  wiring without credentials or startup network calls.
- [x] 3.3 Replace registry-only yfinance route assertions with API tests for commodity, stock-index,
  mixed-provider, canonical-symbol, partial-failure, and cache-reuse behavior.
- [x] 3.4 Retain and test provider-unavailable behavior for yfinance candle and WebSocket routes.

## 4. Documentation And Boundaries

- [x] 4.1 Update API, asset, product, system-design, and tech-stack documentation to mark the ten
  yfinance symbols quote-enabled while candles and WebSocket remain unavailable.
- [x] 4.2 Document `regularMarketPrice`, gateway `receivedAt` semantics, futures proxy/unit caveats,
  and yfinance/Yahoo usage-policy risk.
- [x] 4.3 Update dependency-boundary tests so yfinance imports remain limited to
  `app/providers/` while quote route wiring is now permitted.

## 5. Verification

- [x] 5.1 Run focused provider, router, service, API, registry, candle, and stream tests.
- [x] 5.2 Run the full pytest suite, Ruff checks, Ruff formatting verification, and mypy.
- [x] 5.3 Run strict OpenSpec validation for `add-yfinance-quote-api`.
- [x] 5.4 With network access available, smoke-test all ten yfinance symbols individually and in a
  mixed-provider `/v1/quotes` request, recording latency and symbol-level failures.
