## Why

The gateway contract is incomplete without its final real-time surface: clients can query quotes
and candles over HTTP, but cannot consume normalized market updates as they happen. Adding the
WebSocket stream now completes the MVP contract while reusing the existing symbol registry,
timeframe rules, caches, and candle persistence boundaries.

## What Changes

- Add `WS /v1/stream?symbols=...&timeframe=...` for normalized quote, candle, and connection-status
  events.
- Validate the complete subscription against request limits, enabled canonical symbols, and
  supported timeframes before opening Binance subscriptions.
- Make public stream events provider-agnostic: quote and candle events do not expose
  `assetClass`, `provider`, `providerSymbol`, provider timestamps, or a per-event `stale` flag.
- **BREAKING**: Replace the draft WebSocket event examples in `docs/spec.md` that expose provider
  routing metadata with the minimal public event shapes used by the implemented contract.
- Define deterministic WebSocket status transitions and close behavior for invalid requests,
  provider failures, stale upstream data, slow consumers, and normal disconnects.
- Open official Binance Spot SDK ticker and kline streams lazily, share matching upstream
  subscriptions across downstream clients, and unsubscribe when the final consumer leaves.
- Normalize SDK callbacks behind repository-owned domain models and bounded async queues so a
  slow downstream client cannot block provider consumption or other clients.
- Update the shared latest-quote cache from quote events and maintain current forming candles in
  memory; persist completed stream candles idempotently without blocking live fanout.
- Manage stream tasks and SDK sessions through application lifespan startup/shutdown and add
  focused unit, route, fanout, lifecycle, and persistence tests.
- Update product and system documentation to reflect that `/v1/candles` and `/v1/stream` are
  implemented and to document the final stream contract.

## Capabilities

### New Capabilities

- `market-data-websocket-stream`: Defines subscription validation, public event shapes, status and
  close semantics, Binance stream normalization, shared lazy subscriptions, non-blocking fanout,
  freshness monitoring, and lifecycle cleanup.

### Modified Capabilities

- `latest-quotes`: Allows normalized WebSocket quote events to refresh the process-local quote
  cache while preserving the existing minimal HTTP response and freshness behavior.
- `historical-candles`: Adds current-candle cache updates and idempotent persistence of completed
  candles received from the real-time stream while preserving the existing HTTP contract.

## Impact

- Adds a FastAPI WebSocket route, stream domain models, a Binance Spot WebSocket adapter, a
  process-local stream manager, and a current-candle cache.
- Extends typed configuration for Binance WebSocket URL, reconnect/freshness monitoring, client
  queue capacity, and optional upstream idle cleanup.
- Integrates with the PostgreSQL-backed symbol registry, existing quote cache, candle repository,
  timeframe mapping, and FastAPI lifespan.
- Uses the already locked official `binance-sdk-spot==9.2.0`; no separate WebSocket transport or
  Redis dependency is introduced for the single-process MVP.
- Requires one application worker per process for coherent process-local subscriptions and
  fanout; multi-replica shared streaming remains deferred until a pub/sub layer is introduced.
