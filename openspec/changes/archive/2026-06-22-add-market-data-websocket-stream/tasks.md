## 1. Stream Contract and Configuration

- [x] 1.1 Add typed stream settings for Binance WebSocket URL, SDK reconnect delay, downstream queue capacity, upstream idle grace period, and freshness monitor interval with validated defaults
- [x] 1.2 Add repository-owned stream domain models and protocols for quote, candle, provider-health, status, interest, and downstream event boundaries
- [x] 1.3 Add shared fixed-point Decimal and UTC timestamp serialization helpers and migrate existing quote/candle routes to them without changing HTTP response shapes
- [x] 1.4 Add unit tests for stream query parsing, duplicate preservation rules, symbol limits, supported timeframes, and typed setting validation

## 2. Current Candle and Shared Cache Integration

- [x] 2.1 Implement a lock-owning process-local current-candle cache keyed by canonical symbol and timeframe
- [x] 2.2 Extend the historical candle service to merge an in-range cached forming candle by open time without persisting it
- [x] 2.3 Add stream quote update support to the existing singleton quote cache using gateway receive timestamps
- [x] 2.4 Add unit tests for concurrent candle-cache access, forming-candle replacement/removal, HTTP range filtering, and stream-refreshed HTTP quote reuse

## 3. Binance WebSocket Provider Adapter

- [x] 3.1 Build an official Binance Spot SDK WebSocket Streams client with the configured stream URL and reconnect delay
- [x] 3.2 Implement lazy SDK connection creation and verify that a usable connection exists when the SDK suppresses connection exceptions
- [x] 3.3 Implement serialized ticker subscribe/unsubscribe operations and retain SDK request-stream handles inside the adapter
- [x] 3.4 Implement serialized UTC kline subscribe/unsubscribe operations using the existing public-to-provider timeframe mapping
- [x] 3.5 Normalize ticker SDK models into repository-owned quote events with strict symbol, timestamp, and positive finite Decimal validation
- [x] 3.6 Normalize kline SDK models into repository-owned candle events with strict interval, timestamps, OHLCV, window, and completion validation
- [x] 3.7 Keep synchronous SDK callbacks non-blocking by catching callback errors and using bounded non-blocking ingress queues
- [x] 3.8 Expose sanitized provider connection, reconnect, malformed-event, and terminal-failure signals without leaking SDK models or exceptions
- [x] 3.9 Implement deterministic adapter shutdown that unsubscribes handles and closes SDK connections and sessions
- [x] 3.10 Add adapter tests with fake SDK streams for naming, lowercase provider symbols, callback normalization, malformed payload rejection, connection failure, reconnect signals, unsubscription, and shutdown

## 4. Stream Manager and Shared Interests

- [x] 4.1 Implement process-local quote and candle interest keys, subscriber reference counts, and serialized manager mutation
- [x] 4.2 Open an upstream interest only for its first downstream subscriber and share it across matching clients
- [x] 4.3 Cancel pending idle cleanup when a new subscriber arrives and unsubscribe only after the final subscriber and configured grace period
- [x] 4.4 Consume normalized provider events, update quote/current-candle caches before fanout, and route events only to matching clients
- [x] 4.5 Implement per-client bounded queues, dedicated sender lifecycle, ordered enqueue, overload close code `1013`, and idempotent disconnect cleanup
- [x] 4.6 Implement `CONNECTING`, first-data `SUBSCRIBED`, `STALE`, recovered `SUBSCRIBED`, `RECONNECTING`, and terminal `ERROR` transitions without duplicate status spam
- [x] 4.7 Implement a periodic freshness monitor using `QUOTE_STALE_AFTER_SECONDS` and identify affected canonical symbols and channels
- [x] 4.8 Add stream-manager tests for shared subscriptions, timeframe-specific kline sharing, reference-count cleanup, idle grace cancellation, event filtering, state transitions, and slow-client isolation

## 5. Completed Candle Persistence

- [x] 5.1 Add a bounded completed-candle persistence queue and background worker outside provider callbacks and downstream sender tasks
- [x] 5.2 Remove matching forming state and enqueue idempotent persistence when a normalized stream candle completes
- [x] 5.3 Persist through the existing candle repository in short transactions while allowing live fanout to proceed first
- [x] 5.4 Sanitize and record persistence failures while leaving REST historical gap fill able to recover missing rows
- [x] 5.5 Add unit tests for completed-candle ordering, non-blocking fanout, duplicate upserts, persistence failure isolation, and queue shutdown
- [x] 5.6 Add PostgreSQL integration coverage proving completed streamed candles are upserted once and forming candles are never stored

## 6. FastAPI WebSocket Route

- [x] 6.1 Add `WS /v1/stream` and parse required query parameters without FastAPI default HTTP validation payloads
- [x] 6.2 Resolve all requested symbols through the enabled PostgreSQL registry in one validation step before mutating upstream interests
- [x] 6.3 Reject invalid shape, excessive symbols, unsupported symbols, and unsupported timeframes with close code `1008` and stable close reasons
- [x] 6.4 Reject registry failures with close code `1011` and sanitized `DATABASE_UNAVAILABLE` reason
- [x] 6.5 Register valid clients, emit `CONNECTING`, run sender/disconnect handling, and guarantee manager cleanup in all exit paths
- [x] 6.6 Serialize exact provider-agnostic quote, candle, status, and error event shapes using fixed-point decimals and UTC timestamps
- [x] 6.7 Add WebSocket route tests for validation closes, no partial provider access, exact event fields, status ordering, normal disconnect, overload, and terminal provider failure

## 7. Application Lifespan and Operations

- [x] 7.1 Introduce FastAPI lifespan ownership for the shared stream manager, Binance adapter, ingress consumer, persistence worker, and freshness monitor
- [x] 7.2 Ensure startup creates no Binance connection before the first validated subscriber
- [x] 7.3 Implement deterministic shutdown that stops registration, closes clients, cancels and awaits tasks, unsubscribes interests, and closes SDK resources
- [x] 7.4 Add lifecycle tests for idle startup, active shutdown, repeated cleanup, and absence of leaked or failed background tasks
- [x] 7.5 Add structured logs and available metrics hooks for active clients, upstream interests, reconnects, stale transitions, malformed events, queue overloads, and persistence failures

## 8. Documentation and Verification

- [x] 8.1 Replace provider-specific WebSocket examples in `docs/spec.md` with the final minimal quote, candle, and status contracts and document close codes
- [x] 8.2 Update `docs/system-design.md` to mark candles and streams implemented and describe lifespan, shared interests, queues, caches, freshness, and persistence flow
- [x] 8.3 Update `docs/tech-stack.md` and the environment example with verified official SDK WebSocket usage, single-worker constraint, and stream settings
- [x] 8.4 Run the complete pytest suite including PostgreSQL integration tests when `TEST_DATABASE_URL` is configured
- [x] 8.5 Run Ruff check/format and strict mypy, then resolve all findings
- [x] 8.6 Perform a local smoke test for BTC/USD and ETH/USD quote/candle events, HTTP cache reuse, current-candle visibility, disconnect cleanup, and graceful shutdown
