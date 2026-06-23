## Context

The current `/v1/stream` contract is provider-agnostic for downstream clients, but the runtime
stream provider is Binance-only. The StreamManager already handles downstream validation, lazy
interest sharing, fanout, quote cache updates, current-candle cache updates, completed-candle
persistence, stale monitoring, and provider status signals through a `MarketStreamProvider`
protocol.

Forex support now exists for the current catalog symbols `EUR/USD`, `GBP/USD`, `USD/JPY`, and
`AUD/USD` through Twelve Data REST. Twelve Data's Python SDK also exposes a WebSocket object, but
it is thread-based, uses `websocket-client`, and emits raw JSON dictionaries through an `on_event`
callback. The SDK WebSocket URL targets realtime price quotes, not upstream OHLC/kline streams.

This means Forex streaming cannot mirror the Binance adapter one-for-one. Quotes can be normalized
directly from Twelve Data price events, while candle events must be derived inside Signapse by
bucketizing incoming price ticks into the supported public timeframes.

## Goals / Non-Goals

**Goals:**

- Let `/v1/stream` serve enabled Forex symbols through their persisted `TWELVE_DATA` mapping.
- Preserve the existing downstream quote and candle event shapes.
- Add `MARKET_CLOSED` as a provider-agnostic stream status state for closed-session channels.
- Use exactly one process-local Twelve Data upstream WebSocket connection for Forex streams.
- Route mixed crypto and Forex downstream subscriptions across Binance and Twelve Data providers.
- Normalize Twelve Data price events into quote events.
- Derive Forex OHLC candle events from Twelve Data price ticks.
- Apply the existing Forex weekly quote-session policy to derived Forex candle events.
- Keep SDK imports, raw payloads, callbacks, threads, and exceptions inside `app/providers/`.
- Keep Binance stream behavior unchanged.

**Non-Goals:**

- Do not change REST quote or candle behavior.
- Do not change public quote/candle stream event fields.
- Do not implement holiday calendars, early closes, late opens, or exceptional market closures.
- Do not add Twelve Data streaming for stocks, crypto, commodities, equities, ETFs, or indexes.
- Do not implement multi-replica stream coordination or Redis pub/sub.
- Do not use provider-specific candle streams from Twelve Data unless a later provider capability
  proves they exist and are suitable.
- Do not expose provider plan/entitlement details to clients beyond sanitized provider errors.

## Decisions

### Add a multi-provider stream router instead of rewriting StreamManager

Introduce a `MultiProviderStreamProvider` (or equivalent router) that implements the existing
`MarketStreamProvider` protocol and delegates `subscribe_quote`, `subscribe_candle`, `unsubscribe`,
and `close` by provider name.

The router owns one merged `events` queue. It consumes each child provider's `events` queue in
background tasks and forwards normalized `ProviderStreamEvent` values to the StreamManager.

This keeps the StreamManager mostly provider-agnostic and reuses its existing downstream fanout,
cache, persistence, stale monitoring, and shutdown semantics.

Alternative considered: make StreamManager understand provider groups. That would couple provider
routing to downstream lifecycle logic and make future providers harder to add.

### Use the official Twelve Data SDK but isolate its thread model

Add a `TwelveDataForexStreamProvider` under `app/providers/` that wraps `TDClient.websocket`.
The adapter creates the SDK WebSocket lazily on the first Forex interest and closes it after the
last Forex interest is removed.

Because the SDK invokes `on_event` from its own handler thread, the adapter callback must not touch
async-only objects directly. Instead, capture the running event loop during adapter construction or
connection setup and bridge into the adapter's `asyncio.Queue` using `loop.call_soon_threadsafe`.

The adapter should also run blocking SDK methods such as `connect`, `disconnect`, `subscribe`,
`unsubscribe`, `reset`, and heartbeat interactions outside the ASGI event loop where needed.

Alternative considered: bypass the SDK and use `websockets` directly. The repo guideline prefers
official SDKs when available; direct protocol use can be revisited only if SDK threading or
reconnect behavior proves operationally unsafe.

### Treat Twelve Data WebSocket as quote-only upstream

The Twelve Data SDK WebSocket endpoint is a realtime price stream. The Forex adapter will normalize
price events into `StreamQuote`. It will not expect provider OHLC/kline messages.

For every active Forex candle interest, the adapter will feed accepted price ticks into a
gateway-owned candle builder.

Alternative considered: only support quote events for Forex and omit candle events. That would
break the current `/v1/stream` subscription model, where a valid subscription includes both quote
and candle channels.

### Derive Forex candles from price ticks

Add a small Forex candle builder owned by the Twelve Data stream adapter or a provider-local helper.
For each `(canonical symbol, timeframe)` interest:

1. Align each accepted price event to the timeframe bucket open time in UTC.
2. If no bucket exists, create a forming candle with `open = high = low = close = price`.
3. If the event belongs to the current bucket, update `high`, `low`, and `close`.
4. If the event belongs to a later bucket, emit the previous bucket as `complete=true`, then start
   the new bucket as `complete=false`.
5. Emit a forming candle update whenever the current bucket changes.

Volume is `Decimal("0")` because Twelve Data Forex price events do not provide gateway-compatible
volume and the public candle contract requires non-null volume.

If a price tick skips one or more buckets, the builder must not synthesize missing candles. It only
closes the previous bucket and starts the bucket containing the new tick.

### Apply Forex market-session policy to candle generation

Use the existing market-session policy selected by `SupportedSymbol.asset_class`. Forex quote
events can still be emitted when Twelve Data sends valid prices, but Forex candle events must be
generated only for session-eligible bucket open times.

If a candle interest is outside the Forex weekly quote session, the adapter/router should emit
`MARKET_CLOSED` status for the candle channel instead of waiting for data until the subscription
appears stale.

The current policy intentionally excludes holidays and exceptional closures; this stream design
inherits that limitation.

### Add `MARKET_CLOSED` as a status state

Extend `StreamState` with `MARKET_CLOSED`. A status event remains provider-agnostic and keeps the
existing `type`, `state`, `symbols`, `channels`, and `observedAt` shape.

For Forex candle interests:

- When a subscription is registered entirely outside the weekly candle session, emit
  `MARKET_CLOSED` for channel `candle`.
- When the session closes while subscribed, emit `MARKET_CLOSED` for channel `candle` and stop
  treating the candle interest as stale.
- When the session reopens, return the candle channel to `CONNECTING` until the next valid derived
  candle event arrives, then `SUBSCRIBED`.

Quote channel status remains driven by provider events and stale monitoring.

Alternative considered: reuse `STALE` for closed-market candle channels. That makes a normal market
closure look like a provider/data failure and gives clients no clean way to distinguish operational
staleness from expected session closure.

### Preserve downstream contract and validation

`WS /v1/stream?symbols=...&timeframe=...` remains the only public stream endpoint. Validation still
resolves every canonical symbol from the enabled PostgreSQL registry before provider access.

Mixed subscriptions can include crypto and Forex symbols as long as every symbol is enabled and
the timeframe is supported. The downstream client still receives minimal provider-agnostic quote,
candle, and status events.

Provider entitlement failures, invalid API key, or upstream connection failure map to sanitized
`PROVIDER_UNAVAILABLE` errors and WebSocket close code `1011` for affected subscriptions.

## Risks / Trade-offs

- **Twelve Data SDK WebSocket is thread-based** -> Isolate it inside the provider adapter and use
  thread-safe event-loop bridging.
- **Payload shape is raw JSON and may differ by provider entitlement or asset** -> Add focused
  normalization tests with captured fixture payloads and reject unknown/malformed events without
  leaking raw payloads.
- **Free plan may allow only one WebSocket connection** -> Use one process-local Twelve Data
  connection and multiplex symbols on it; document single-process limitation.
- **Derived candles depend on tick frequency** -> Preserve natural gaps and do not synthesize
  missing candles; REST historical candles remain authoritative for backfill.
- **Candle close is only known after a later tick or shutdown** -> Emit completion when a later
  bucket arrives. Do not invent timer-only closes without a price event in the next bucket.
- **Market close can otherwise look stale** -> Add `MARKET_CLOSED` state and exclude closed candle
  interests from stale evaluation.
- **One downstream subscription can mix providers** -> Use router-level provider isolation so a
  Twelve Data failure does not necessarily imply Binance interests are broken, while still
  delivering coherent status events to affected clients.
- **No cross-process stream sharing** -> Keep the current MVP single-worker/process-local stream
  assumption; later Redis/pub-sub work can centralize provider stream consumption.

## Migration Plan

1. Add typed settings for Twelve Data WebSocket configuration and heartbeat cadence.
2. Add the multi-provider stream router and wire FastAPI lifespan with Binance plus optional Twelve
   Data stream providers.
3. Add the Twelve Data Forex stream adapter behind the provider boundary.
4. Add Forex candle builder and market-session status behavior.
5. Update downstream serialization and status enum to include `MARKET_CLOSED`.
6. Add unit, route, and lifecycle tests.
7. Update docs and runbook with Forex stream examples and the new status state.

Rollback can disable the Twelve Data stream provider wiring and leave Binance streaming unchanged.
No database schema migration is required.

## Open Questions

- We should capture at least one real Twelve Data WebSocket price payload from the user's free-plan
  key before implementation or during the first test spike, because the SDK exposes raw JSON and
  the precise field names must drive normalization.
- If a subscription includes only Forex candle channels that are currently market-closed, should
  the connection stay open indefinitely with `MARKET_CLOSED`, or should product later add a
  client-controlled channel selection? This change keeps the connection open.
