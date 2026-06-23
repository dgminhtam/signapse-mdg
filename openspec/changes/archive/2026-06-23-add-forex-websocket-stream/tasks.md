## 1. Stream Domain and Contract

- [x] 1.1 Add `MARKET_CLOSED` to the stream status state domain type.
- [x] 1.2 Update stream event serialization so `MARKET_CLOSED` status keeps the existing status event shape.
- [x] 1.3 Add tests for exact `MARKET_CLOSED` status serialization.
- [x] 1.4 Update request/route tests to keep existing validation behavior unchanged for crypto streams.

## 2. Multi-Provider Stream Routing

- [x] 2.1 Add a provider-router implementation of `MarketStreamProvider` that delegates by persisted provider name.
- [x] 2.2 Merge child provider event queues into one router event queue without blocking child providers.
- [x] 2.3 Route quote interests by `SupportedSymbol.provider`.
- [x] 2.4 Route candle interests by `SupportedSymbol.provider` and timeframe provider interval.
- [x] 2.5 Unsubscribe and close provider-specific interests idempotently.
- [x] 2.6 Add tests for mixed Binance/Twelve Data subscriptions and provider failure isolation.
- [x] 2.7 Preserve current Binance-only behavior when only Binance symbols are requested.

## 3. Twelve Data Forex WebSocket Adapter

- [x] 3.1 Define adapter protocols for the subset of `TDClient.websocket` and SDK WebSocket methods used.
- [x] 3.2 Build a `TwelveDataForexStreamProvider` behind `app/providers/` with no SDK types leaking outward.
- [x] 3.3 Lazily create one SDK WebSocket connection on the first Forex stream interest.
- [x] 3.4 Subscribe and unsubscribe Twelve Data provider symbols dynamically on the shared connection.
- [x] 3.5 Bridge SDK thread callbacks to the adapter's asyncio event queue using thread-safe loop scheduling.
- [x] 3.6 Run blocking SDK connect/disconnect/subscribe/unsubscribe interactions outside the ASGI event loop where needed.
- [x] 3.7 Send heartbeat on a configurable cadence while the Twelve Data connection is active.
- [x] 3.8 Map SDK or entitlement failures to sanitized provider-unavailable signals.
- [x] 3.9 Capture or fixture at least one real Twelve Data free-plan WebSocket price payload before finalizing normalization assumptions.
- [x] 3.10 Add tests for lazy connect, shared connection reuse, dynamic subscribe/unsubscribe, heartbeat, shutdown cleanup, and callback bridging.

## 4. Forex Quote Event Normalization

- [x] 4.1 Normalize valid Twelve Data price events into `StreamQuote` using canonical symbol metadata.
- [x] 4.2 Validate provider symbol, finite positive decimal price, and event type or timestamp fields from raw payloads.
- [x] 4.3 Reject malformed, unknown-symbol, duplicate-unexpected, or non-price events without fanout.
- [x] 4.4 Ensure successful public quote events still expose only `type`, `symbol`, `price`, and `receivedAt`.
- [x] 4.5 Add provider tests for valid Forex quote events and malformed payload rejection.

## 5. Forex Candle Builder

- [x] 5.1 Add a provider-local Forex candle builder keyed by canonical `(symbol, timeframe)`.
- [x] 5.2 Align accepted price ticks to supported timeframe bucket open times in UTC.
- [x] 5.3 Emit first-tick forming candles with OHLC equal to price and volume decimal zero.
- [x] 5.4 Update current bucket high, low, and close on later ticks inside the same bucket.
- [x] 5.5 Emit the previous bucket as complete when a later bucket receives a tick.
- [x] 5.6 Start the new bucket as forming after closing the previous bucket.
- [x] 5.7 Preserve natural gaps by not synthesizing skipped buckets.
- [x] 5.8 Support all public stream timeframes currently accepted by `/v1/stream`.
- [x] 5.9 Add builder tests for 1m, 5m, 15m, 1h, and 1d bucket boundaries.
- [x] 5.10 Add tests for zero-volume serialization and no synthetic skipped candles.

## 6. Market Session Stream Semantics

- [x] 6.1 Reuse the existing market-session policy selector for streamed Forex candle buckets.
- [x] 6.2 Exclude intraday Forex candle buckets outside Sunday 17:00 through Friday 17:00 New York time.
- [x] 6.3 Exclude Forex `1d` candle buckets labeled Saturday or Sunday in UTC.
- [x] 6.4 Emit `MARKET_CLOSED` for closed Forex candle interests on registration.
- [x] 6.5 Transition closed Forex candle interests back to `CONNECTING` when the session reopens.
- [x] 6.6 Exclude market-closed candle interests from stale evaluation.
- [x] 6.7 Keep Forex quote channel status independent from candle market-closed status.
- [x] 6.8 Add DST-aware tests for Friday close, Sunday reopen, winter boundaries, and daily labels.

## 7. Stream Manager Cache and Persistence Guardrails

- [x] 7.1 Filter stream candle cache writes through the symbol's market-session policy.
- [x] 7.2 Filter completed stream candle persistence through the symbol's market-session policy.
- [x] 7.3 Ensure ineligible streamed Forex candles are not exposed later through `/v1/candles`.
- [x] 7.4 Preserve Binance cache and completed-candle persistence behavior.
- [x] 7.5 Add tests for ineligible streamed Forex candle cache/persistence rejection.

## 8. Application Wiring and Configuration

- [x] 8.1 Add typed settings for Twelve Data WebSocket enablement or base behavior, heartbeat cadence, and queue limits as needed.
- [x] 8.2 Wire FastAPI lifespan to build Binance and Twelve Data stream providers behind the multi-provider router.
- [x] 8.3 Allow startup without `TWELVEDATA_API_KEY` while rejecting live Forex stream fills with sanitized provider errors.
- [x] 8.4 Ensure shutdown closes router child tasks, Binance provider, and Twelve Data provider deterministically.
- [x] 8.5 Add lifecycle tests for startup with no clients, mixed clients, and shutdown with active Forex streams.

## 9. Documentation and Runbook

- [x] 9.1 Update `docs/spec.md` with Forex stream support and `MARKET_CLOSED`.
- [x] 9.2 Update `docs/system-design.md` with multi-provider stream routing and derived Forex candle flow.
- [x] 9.3 Update `docs/tech-stack.md` with Twelve Data WebSocket SDK/threading notes and one-connection free-plan constraint.
- [x] 9.4 Update README with Postman/browser stream examples for Forex and mixed subscriptions.
- [x] 9.5 Document that Forex stream candles are derived from price ticks and REST historical candles remain authoritative for backfill.
- [x] 9.6 Document that holidays and exceptional closures remain out of scope.

## 10. Verification

- [x] 10.1 Run `openspec validate add-forex-websocket-stream --strict`.
- [x] 10.2 Run Twelve Data stream adapter and Forex candle builder tests.
- [x] 10.3 Run stream manager, stream route, and lifecycle tests.
- [x] 10.4 Run quote/candle REST regression tests.
- [x] 10.5 Run complete unit test suite.
- [x] 10.6 Run relevant integration tests when `TEST_DATABASE_URL` is available.
- [x] 10.7 Run `ruff check .`, `mypy app`, and `git diff --check`.
