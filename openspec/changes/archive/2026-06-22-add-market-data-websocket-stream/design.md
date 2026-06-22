## Context

The gateway already exposes registry-backed symbols, latest quotes, and historical candles.
Quotes use a process-local cache; closed candles use PostgreSQL; and Binance REST access is isolated
behind the official Spot SDK adapter. The final MVP contract adds a WebSocket endpoint that emits
both quote and candle updates for multiple canonical symbols and one timeframe.

The official `binance-sdk-spot==9.2.0` includes asynchronous WebSocket Streams APIs, generated
ticker and kline models, subscribe/unsubscribe handles, connection pooling, scheduled reconnect,
and resubscription. Its message callbacks are synchronous and some connection/reconnect failures
are logged internally rather than exposed through a stable public lifecycle hook. The gateway must
therefore wrap the SDK carefully instead of allowing SDK callbacks or models to become application
boundaries.

The deployment target remains one Uvicorn worker per process. All subscriptions, fanout state,
latest quotes, and current candles are process-local. PostgreSQL remains the only durable store and
Redis/pub-sub is intentionally deferred.

## Goals / Non-Goals

**Goals:**

- Complete the provider-agnostic MVP with `WS /v1/stream`.
- Emit deterministic minimal quote, candle, and status events.
- Share lazy Binance ticker and kline interests across downstream clients.
- Keep provider consumption non-blocking and isolate slow clients.
- Feed streamed quotes and candles into existing cache and persistence paths.
- Detect stale/reconnecting upstream state and clean up all resources on disconnect or shutdown.
- Preserve typed boundaries and make behavior testable without a live Binance connection.

**Non-Goals:**

- Dynamic subscribe/unsubscribe messages after a downstream WebSocket is connected.
- Authentication, authorization, public quotas, or internet-facing abuse protection.
- Exactly-once delivery, durable replay, sequence numbers, or reconnect gap backfill.
- Cross-process fanout, Redis, or support for multiple application workers sharing live state.
- Additional providers, symbols, event types, or timeframes beyond the existing registry and map.
- Persisting every forming-candle update.

## Decisions

### 1. Use one query-defined downstream subscription

The route accepts `symbols` and `timeframe` in the WebSocket URL. A connection subscribes to both
quotes and candles for the full validated set and remains immutable until disconnect.

This matches the documented MVP contract and keeps connection state, validation, and cleanup
small. A client that needs a different set opens another connection.

Alternative considered: accept JSON subscribe/unsubscribe commands. That adds a command protocol,
acknowledgements, partial mutation failures, and more synchronization than the current consumer
requires.

### 2. Make all public stream events provider-agnostic

Quote events expose only `type`, canonical `symbol`, fixed-point `price`, and gateway
`receivedAt`. Candle events expose `type`, canonical series identity, the same candle fields as the
HTTP endpoint, and `receivedAt`. Provider identity, provider symbol, asset class, provider time,
and per-event stale flags remain internal.

Status events contain `type`, `state`, affected canonical `symbols`, affected `channels`, and
`observedAt`; `ERROR` additionally carries a stable sanitized `code` and `message`.

This deliberately replaces the older draft examples in `docs/spec.md`. It aligns streaming with
the finalized HTTP contracts and prevents clients from depending on Binance routing details.

Alternative considered: retain provider metadata for diagnostics. Operational diagnostics belong
in structured logs and metrics, not the consumer contract.

### 3. Validate the entire request before upstream mutation

Parsing reuses the quote symbol rules and configured distinct-symbol limit. All canonical symbols
are loaded from the enabled PostgreSQL registry in one operation and the timeframe is resolved
through the existing map. Any unsupported symbol rejects the complete subscription rather than
creating a partial stream.

Policy violations close with `1008` and a stable reason code. Registry/internal failures close
with `1011`. No upstream reference count changes until validation succeeds.

Alternative considered: partial subscription with symbol-level errors. Unlike an HTTP batch,
long-lived partial stream state is easy for clients to misunderstand and hard to recover
atomically.

### 4. Wrap the official SDK in a queue-based provider adapter

The provider adapter owns `ConfigurationWebSocketStreams`, `Spot.websocket_streams`, SDK handles,
and provider-to-canonical mappings. It calls `create_connection()` lazily, then the SDK `ticker()`
and `kline()` operations. SDK callbacks perform only strict normalization plus a non-blocking
enqueue into an adapter-owned bounded ingress queue.

A dedicated async consumer publishes repository-owned `StreamQuote` and `StreamCandle` events to
the manager. Callback exceptions are caught and converted to sanitized health/error signals so
they cannot escape into the SDK receive loop.

The adapter verifies that connection creation actually produced an active SDK connection because
the SDK can log and suppress connection exceptions.

Alternative considered: direct use of `websockets` or `aiohttp`. Direct protocol control would
provide clearer reconnect hooks, but it would duplicate official SDK subscription, ping, reconnect,
and resubscribe behavior without a demonstrated requirement that the SDK cannot satisfy.

### 5. Use interest keys and reference counts

The manager uses:

- Quote interest key: `(canonical_symbol, "quote")`
- Candle interest key: `(canonical_symbol, "candle", timeframe)`

Each interest stores the enabled registry mapping, downstream subscriber IDs, upstream handle,
last-valid-event time, and health state. The first subscriber opens the SDK interest; later clients
share it. The final departure schedules cleanup after a configurable idle grace period. A new
subscriber during the grace period cancels cleanup.

Ticker interests are shared across clients regardless of candle timeframe. Kline interests are
shared only for the same symbol and timeframe.

Alternative considered: one combined Binance connection per downstream client. That is simpler
locally but multiplies upstream load and reconnect work and violates the lazy shared-stream design.

### 6. Treat readiness and freshness as derived state

After validation the route accepts the connection and emits `CONNECTING`. A downstream
subscription becomes `SUBSCRIBED` only when every required ticker and kline interest has delivered
at least one valid event.

A periodic monitor compares each interest's last-valid-event time with
`QUOTE_STALE_AFTER_SECONDS`. If an interest exceeds the threshold, affected clients receive one
state-transition `STALE` event identifying symbols and channels. Once all interests are fresh,
they receive one `SUBSCRIBED` recovery event.

The adapter emits `RECONNECTING` when SDK connection loss/reconnect is observable. The freshness
monitor remains the safety net where SDK internals do not expose a reliable transition. Status
events are emitted only on state changes, not on every monitor tick.

Alternative considered: mark `SUBSCRIBED` immediately after SDK subscribe calls. The SDK operation
does not provide a sufficiently strong data-readiness acknowledgement.

### 7. Isolate each downstream client with a bounded queue

Every client registration owns a bounded `asyncio.Queue` and one sender task. The manager fans out
by `put_nowait`; it never awaits network writes in provider or cache consumers. Queue order defines
the event order observed by that client.

If the queue is full, the manager marks the client overloaded, closes it with `1013`, and removes
its references. This favors service health and fresh data over silently accumulating latency.

Alternative considered: drop intermediate candle or quote events. Silent loss would require
sequence or snapshot semantics that the contract does not currently provide.

### 8. Share quote cache and introduce a current-candle cache

Valid stream quotes are written to the existing singleton `QuoteCache` before fanout. Existing HTTP
TTL and stale calculations continue to use gateway `received_at`.

A new lock-owning `CandleCache` stores one forming candle per `(symbol, timeframe)`. The historical
candle service reads a matching cached forming candle after its repository/provider work and
merges it by open time. Completed events remove matching forming state.

All Decimal serialization uses fixed-point formatting, preserving scale and preventing values such
as `0E-8` from leaking into public JSON.

Alternative considered: separate stream-only caches. That would duplicate state and prevent HTTP
requests from benefiting from already-consumed real-time data.

### 9. Persist completed candles asynchronously through the existing repository

When a normalized kline has `complete=true`, live fanout and current-cache removal happen
immediately, and the candle is placed on a bounded persistence queue. A worker batches or
serializes calls to the existing idempotent `upsert_complete` repository method using short
transactions.

Persistence failure is logged and measured but does not terminate streaming. A later historical
HTTP request can recover a missing closed candle using the existing REST gap-fill path.

Alternative considered: await PostgreSQL before fanout. That couples real-time latency and stream
availability to database latency.

### 10. Own long-lived resources in FastAPI lifespan

The application lifespan constructs the shared manager/provider resources and starts only local
monitor/consumer workers; it does not connect to Binance. The first validated subscriber causes
the upstream connection. Shutdown stops accepting work, closes downstream clients, cancels and
awaits workers, unsubscribes SDK handles, closes SDK WebSocket/session resources, and then disposes
remaining state.

Route dependencies retrieve the app-owned manager rather than creating cached global objects.
Tests can replace the manager/provider with deterministic fakes.

Alternative considered: module-level `lru_cache` singletons. They are convenient for HTTP helpers
but make async task ownership, test isolation, and shutdown nondeterministic.

## Risks / Trade-offs

- [SDK reconnect lifecycle is only partially observable] → Wrap connection creation, inspect
  adapter-owned connection state conservatively, emit reconnect signals when observable, and use
  the freshness monitor as the contract-level fallback.
- [SDK stream registries are process-global] → Own exactly one Spot WebSocket Streams instance per
  application process and serialize subscribe/unsubscribe mutation inside the adapter.
- [One worker is a scaling constraint] → Document and enforce the single-worker MVP deployment;
  introduce Redis/pub-sub and centralized provider consumption before horizontal live scaling.
- [A completed candle can be streamed but fail persistence] → Keep fanout available, log/measure
  the failure, and rely on idempotent REST historical fill for later recovery.
- [Bounded queues can disconnect temporarily slow consumers] → Use a configurable capacity,
  expose close code `1013`, and keep the initial internal consumer capacity comfortably above
  expected burst size.
- [Ticker and kline events are not an atomic pair] → Preserve arrival order per client queue and do
  not imply cross-channel snapshot consistency.
- [No replay means reconnect gaps are possible] → State this explicitly; clients use HTTP quotes
  and candles to recover snapshots after reconnect.
- [Database validation occurs before each connection] → Keep the read short and batch all requested
  symbols; caching registry records is deferred until connection volume justifies it.

## Migration Plan

1. Add typed stream settings and repository/domain abstractions without enabling the route.
2. Add provider normalization, caches, manager, and deterministic fake-based tests.
3. Wire FastAPI lifespan and `/v1/stream`, then update `docs/spec.md`, `docs/system-design.md`,
   `docs/tech-stack.md`, and the environment example.
4. Deploy with one application worker and run a smoke test for BTC/USD and ETH/USD ticker/kline
   events, disconnect cleanup, and HTTP cache reuse.
5. Monitor active clients, upstream reconnects, stale transitions, queue overflows, provider
   errors, and candle persistence failures.

Rollback removes or disables the WebSocket route and shuts down the manager. Existing HTTP
contracts and PostgreSQL schema remain compatible; no destructive migration is required.

## Open Questions

- None blocking implementation. Queue capacity, idle grace, reconnect delay, and monitor interval
  defaults can be selected conservatively in implementation and documented with the typed
  settings.
