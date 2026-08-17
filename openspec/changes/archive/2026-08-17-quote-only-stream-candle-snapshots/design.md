## Context

The current stream path treats a WebSocket subscription as a quote-and-candle subscription. The
request parser requires a stream timeframe, `StreamManager` registers `QuoteInterest` and
`CandleInterest` objects, and provider adapters either subscribe to kline streams or derive
candles from price ticks. Stream candles also update the process-local candle cache and enqueue
completed-candle persistence. This makes the lifecycle, session policy, and provider surface of a
quote stream depend on OHLC aggregation.

The existing `GET /v1/candles` path already resolves Provider Selection, reads complete candles
from PostgreSQL, fills gaps through the selected candle provider, and preserves the public candle
response shape. Its in-memory cache is currently populated primarily by the WebSocket candle
path, so the REST service must become the owner of forming-candle snapshots when that path is
removed.

The implementation is constrained to the async FastAPI gateway, its process-local state, the
existing provider adapters and repository boundaries, and a coordinated breaking update to the
internal Java client. No shared cache, new public endpoint, provider fallback, or public payload
metadata is required.

## Goals / Non-Goals

**Goals:**

- Make `WS /v1/stream` a quote-only subscription with no timeframe parameter.
- Preserve normalized quote events, quote cache updates, multi-symbol/provider-selection behavior,
  and quote lifecycle status semantics.
- Remove WebSocket candle interests, derived candle events, candle session lifecycle, and stream
  candle persistence from the gateway's live path.
- Make `GET /v1/candles` independently serve completed and forming candles, including the latest
  eligible candle for `limit=1`.
- Add a process-local, Provider-Selection-isolated forming snapshot cache with a five-second
  default TTL, per-key single-flight loading, deterministic expiry, and sanitized `503`
  `PROVIDER_UNAVAILABLE` failure behavior.
- Preserve existing HTTP candle and WebSocket quote/status shapes.

**Non-Goals:**

- Adding `/v2/stream`, `/v1/current-candle`, a `channels` query parameter, or a compatibility
  feature flag.
- Supporting candle events, candle subscriptions, or candle aggregation over WebSocket.
- Introducing Redis, pub/sub, a distributed cache, a polling `429`, or provider fallback.
- Changing historical timeframe support, candle response fields, quote event fields, status event
  fields, or public provider metadata.
- Implementing the Java client in this repository.

## Decisions

### 1. Enforce a quote-only WebSocket boundary

The route will parse `symbols` and the optional request-wide `provider` as before, but any
presence of the `timeframe` query parameter—including empty or otherwise valid candle values—will
be rejected before registry or provider access. The close remains WebSocket `1008`, with the
specific reason `TIMEFRAME_NOT_ALLOWED`. Rejection telemetry will retain safe request context such
as request ID, symbols, submitted timeframe, operation, and error code.

The stream request model will no longer carry a timeframe. `StreamManager` registrations and
upstream interest keys will contain quote interests only. This is preferred over accepting and
ignoring timeframe because the latter would preserve a misleading contract and make client
mistakes invisible.

### 2. Keep quote lifecycle and cache behavior, remove candle plumbing end to end

The manager will create one quote interest per distinct canonical symbol and selected Provider
Mapping, share matching interests, and retain the existing bounded per-client fanout queue. Every
valid normalized provider quote will update `QuoteCache` before fanout; no initial quote snapshot
will be synthesized. `CONNECTING` is emitted at registration, `SUBSCRIBED` after the first valid
quote, and `STALE` is based only on the quote freshness threshold. A fresh quote restores
`SUBSCRIBED`; provider reconnects emit `RECONNECTING`; unrecoverable provider failures emit the
existing sanitized `ERROR` and close with `1011`. `MARKET_CLOSED` is not part of the quote-only
stream.

Provider WebSocket adapters will subscribe and normalize ticker/price events only. Kline stream
subscriptions, tick-to-candle aggregation, candle event fanout, stream candle cache writes, and
stream candle persistence queues will be deleted or bypassed at their owning boundaries rather
than hidden behind the public route. REST candle adapters remain available for `CandleService`.

Keeping the quote path and deleting only its candle branches minimizes contract drift while
ensuring a future REST candle request never depends on an active WebSocket client.

### 3. Make the REST candle service the forming-snapshot owner

Introduce an explicit process-local forming snapshot cache (or evolve the current candle-cache
module into that role) with entries containing:

- canonical symbol,
- selected Provider Identifier and provider symbol,
- timeframe,
- the normalized forming `Candle`, and
- the gateway time at which the snapshot was stored.

The exact key is therefore `(canonical symbol, provider, provider symbol, timeframe)`. The cache
will use the injected service clock for TTL and close-time decisions and maintain an independent
`asyncio.Lock` per key. A cache miss or expired entry acquires only that key's lock, checks the
cache again, and allows one provider fill; concurrent callers for other keys remain independent.

`CandleService` will continue to use PostgreSQL for complete candles and the selected provider
for missing ranges. After normalization, a candle with `close_time` still in the future is stored
as a forming snapshot with the configured TTL; complete candles are upserted through the existing
repository boundary. A forming entry whose current time has reached its `close_time` is evicted,
not relabeled as complete, so the normal persisted/provider path supplies the completed value.

For `limit=1`, the service will select the latest eligible available result: a fresh forming
snapshot wins when its open time is the latest eligible candle; otherwise the latest completed
candle is returned. If neither exists, the endpoint returns `candles: []`. A fresh forming cache
hit is served without a provider request. An expired entry is removed before refresh; if refresh
fails, the service raises the existing sanitized provider-unavailable boundary and never returns
the expired forming value. Polling faster than the TTL is served from the cache and is not
rejected with `429`.

Completed-candle persistence and reuse remain outside the forming snapshot TTL. Cache entries are
never shared between Provider Selections or timeframes, even when the canonical symbol is the
same.

This is preferred over fetching the provider on every forming-candle poll because it reduces
provider load while keeping the five-second freshness contract. It is preferred over continuing
to depend on the WebSocket because the HTTP candle API must work for clients that do not subscribe
to quotes.

### 4. Preserve public contracts and provider routing

The quote event remains exactly `type`, `symbol`, `price`, and `receivedAt`. Status events retain
their existing fields and lifecycle states, except that `channels` is always `["quote"]` and
`MARKET_CLOSED` is not emitted. Candle response fields remain unchanged, including `complete` and
fixed-point decimal serialization. Provider Override remains optional, exact, request-wide, and
without fallback; cache and persistence identity use the resolved Provider Selection.

### 5. Coordinate the breaking rollout

The gateway contract and Java client will be released together during one maintenance window. The
release updates the Java client to omit `timeframe` from quote-stream URLs and to consume quote-only
events/statuses, while candle consumers call `GET /v1/candles` with an explicit timeframe. There is
no mixed-version compatibility window. Rollback means restoring the previous gateway and matching
client release as a pair; the new process-local cache has no schema or shared-state migration.

## Risks / Trade-offs

- **[Breaking client contract]** Existing clients that send `timeframe` or expect candle events
  will disconnect or stop receiving those events. → Release the gateway and Java client together,
  document the exact close reason, and add public boundary tests for both accepted and rejected
  URLs.
- **[Provider load shifts to HTTP polling]** Candle consumers may poll more often after moving off
  the WebSocket. → Serve fresh forming snapshots for five seconds, single-flight identical misses,
  and expose no stale value after expiry.
- **[Process-local cache is not shared]** Multiple gateway processes can issue independent candle
  fills. → Keep the MVP single-process and make the cache key/TTL behavior explicit; defer a shared
  cache until deployment topology requires it.
- **[Provider close-time race]** A forming snapshot can cross its interval boundary between cache
  lookup and response. → Check close time with the injected clock on every read and evict at the
  boundary rather than marking the cached object complete.
- **[Removed stream persistence path]** Completed candles that were previously captured from live
  ticks may be persisted later through HTTP/provider fills. → Preserve idempotent REST fills and
  add tests proving the candle endpoint remains usable without a stream registration.

## Migration Plan

1. Implement and test the quote-only stream and self-contained forming snapshot behavior behind the
   existing `/v1` paths.
2. Update `docs/spec.md`, `docs/system-design.md`, environment settings documentation, and the
   Java client contract in the same release package.
3. Deploy gateway and Java client together; verify quote events, quote lifecycle statuses, and
   `GET /v1/candles?limit=1` for both forming and completed results.
4. Roll back the gateway and Java client together if contract or provider behavior is invalid.

## Open Questions

- None for the MVP. The timeframe rejection reason, five-second default TTL, process-local cache,
  single-flight behavior, status semantics, response shapes, and coordinated rollout have been
  confirmed.
