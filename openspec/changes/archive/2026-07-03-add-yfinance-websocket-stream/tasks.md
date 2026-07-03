## 1. Shared Tick Candle Foundation

- [x] 1.1 Extract or introduce a provider-owned price-tick candle builder with UTC timeframe
  bucketing, forming and completed candle emission, no gap synthesis, and configurable zero volume.
- [x] 1.2 Migrate the Twelve Data stream adapter to the shared builder without changing its public
  quote, candle, market-session, or lifecycle behavior.
- [x] 1.3 Add or update focused tests proving the shared builder preserves same-bucket updates,
  later-bucket completion, skipped-bucket behavior, UTC alignment, and session filtering.

## 2. YFINANCE Async WebSocket Adapter

- [x] 2.1 Add an injectable yfinance stream client protocol and factory around
  `yfinance.AsyncWebSocket(verbose=False)` while keeping all yfinance imports inside
  `app/providers/`.
- [x] 2.2 Implement the YFINANCE stream provider allowlist, canonical/provider-symbol lookup, quote
  interests, candle timeframe interests, and provider-symbol reference counting.
- [x] 2.3 Implement lazy first-subscription setup, one shared listener task, idempotent subscribe,
  provider-symbol unsubscribe, final-interest disconnect, and deterministic `close()`.
- [x] 2.4 Normalize decoded `id`, `price`, and optional `time` fields into finite positive Decimal
  price ticks with UTC provider and receive timestamps.
- [x] 2.5 Emit normalized `StreamQuote` events for active quote interests and derive `1m`, `5m`,
  `15m`, `1h`, and `1d` `StreamCandle` events with decimal zero volume.
- [x] 2.6 Reject malformed, unsupported, inactive, or non-price payloads without exposing provider
  details or updating downstream state.
- [x] 2.7 Implement listener supervision that emits `RECONNECTING`, waits the configured provider
  reconnect delay, creates a fresh client, and resubscribes current symbols after visible listener
  termination.
- [x] 2.8 Preserve cancellation as lifecycle control and map initial connection, subscription, and
  unrecoverable provider failures to the sanitized provider-unavailable boundary.

## 3. Stream Routing And Lifespan Wiring

- [x] 3.1 Register the YFINANCE stream provider in `MultiProviderStreamProvider` through FastAPI
  lifespan using the existing provider queue capacity and reconnect delay settings.
- [x] 3.2 Expose the YFINANCE stream provider on application state for lifecycle verification while
  ensuring startup creates no SDK client, connection, subscription, or background task.
- [x] 3.3 Update stream router and dependency-boundary coverage so persisted `YFINANCE` mappings
  route only to the new adapter with no provider fallback or symbol remapping.

## 4. Adapter And Contract Tests

- [x] 4.1 Add unit tests for lazy connection, shared multi-symbol subscription, quote/candle
  reference counts, idempotent operations, final-symbol unsubscribe, and final connection close.
- [x] 4.2 Add unit tests for valid tick normalization, millisecond and second timestamps, Decimal
  conversion, canonical symbol mapping, and optional provider time.
- [x] 4.3 Add unit tests rejecting unknown symbols, invalid prices, malformed timestamps, inactive
  interests, duplicate setup, and queue overflow without raw provider exposure.
- [x] 4.4 Add unit tests proving Yahoo day volume is ignored and tick-derived candles use zero
  volume, complete prior buckets, and do not synthesize gaps.
- [x] 4.5 Add unit tests proving a successful silent subscription emits no fabricated event or
  provider error and remains eligible for the stream manager's initial `CONNECTING` state.
- [x] 4.6 Add unit tests for listener failure signals, fresh-client reconstruction,
  resubscription, cancellation, unsubscribe failure isolation, and deterministic shutdown.
- [x] 4.7 Extend lifespan, stream provider router, stream manager, and WebSocket API tests for
  YFINANCE-only and mixed Binance/Twelve Data/YFINANCE subscriptions.
- [x] 4.8 Verify existing Binance and Twelve Data stream regression tests still pass after shared
  candle-builder extraction and YFINANCE wiring.

## 5. Documentation And Validation

- [x] 5.1 Update `docs/spec.md`, `docs/api-contract.md`, `docs/system-design.md`,
  `docs/tech-stack.md`, and `docs/assets.md` to describe YFINANCE AsyncWebSocket routing,
  tick-derived zero-volume candles, lazy lifecycle, and non-guaranteed Yahoo event coverage.
- [x] 5.2 Remove obsolete documentation and tests that state YFINANCE WebSocket routing is
  unavailable while retaining Yahoo/yfinance usage-policy and futures-proxy caveats.
- [x] 5.3 Run focused stream tests and the full pytest suite, then run Ruff format/check and strict
  mypy validation.
- [x] 5.4 Run strict OpenSpec validation and a bounded live yfinance WebSocket smoke test that
  verifies connection/subscription mechanics without requiring every approved symbol to emit.
