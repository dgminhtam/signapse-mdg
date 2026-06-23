## Context

The gateway already routes WebSocket interests through `MultiProviderStreamProvider`, shares exact
interests in `StreamManager`, normalizes provider events into `StreamQuote` and `StreamCandle`, and
fans them out through the provider-agnostic `/v1/stream` contract. Binance supplies native ticker
and kline streams. Twelve Data supplies price ticks from one shared SDK WebSocket and the gateway
derives candles locally.

The registry also contains ten enabled `YFINANCE` mappings:

```text
XAG/USD -> SI=F       BRENT  -> BZ=F       NATGAS -> NG=F
COFFEE  -> KC=F       SUGAR  -> SB=F       WHEAT  -> ZW=F
CORN    -> ZC=F       SPX    -> ^GSPC      NDX    -> ^NDX
DJI     -> ^DJI
```

yfinance 1.4.1 exposes `AsyncWebSocket` with `subscribe`, `unsubscribe`, `listen`, and `close`
operations. Its decoded `PricingData` payload contains a provider symbol, price, provider time,
exchange metadata, and optional day-level values, but no interval OHLC candle. Live research on
June 23, 2026 confirmed that the client can connect and emit ticks for some Yahoo instruments, while
the ten current mappings may remain silent. This change intentionally treats successful
subscription separately from event availability so the gateway can complete provider coverage now
without changing its public contract.

## Goals / Non-Goals

**Goals:**

- Serve quote and candle stream interests for all ten enabled `YFINANCE` mappings.
- Keep all yfinance clients, payloads, configuration, and exceptions inside `app/providers/`.
- Use one lazy process-local yfinance asynchronous WebSocket and share each provider-symbol
  subscription across quote and candle interests.
- Normalize valid Yahoo price ticks into existing domain stream events.
- Derive all supported candle timeframes from accepted price ticks with decimal zero volume.
- Supervise listener termination, reconnect with the existing provider reconnect delay, resubscribe
  active symbols, and clean up deterministically.
- Preserve provider isolation so another stream provider can be introduced later without changing
  `/v1/stream`.

**Non-Goals:**

- Do not guarantee that Yahoo emits events for every accepted provider symbol.
- Do not add polling, REST snapshots, ETF proxy remapping, or cross-provider fallback.
- Do not expose Yahoo fields, provider identity, futures units, or exchange metadata publicly.
- Do not add native Yahoo candle handling because the WebSocket supplies price ticks rather than
  interval OHLCV.
- Do not add precise commodity futures or index market-session calendars in this change.
- Do not change registry rows, database schema, public WebSocket event shapes, or close codes.

## Decisions

### Use `yfinance.AsyncWebSocket` behind a dedicated stream adapter

Create a yfinance stream adapter that implements the existing `MarketStreamProvider` protocol and
constructs `AsyncWebSocket(verbose=False)` through an injectable client factory. The adapter will be
registered under `YFINANCE` in the existing multi-provider router.

The stream adapter will remain separate from `yfinance_market_data.py`. The REST adapter owns a
synchronous shared session, request timeout patching, and serialized worker-thread work, while the
stream adapter owns an async connection and background listener. They may share the approved
provider-symbol allowlist, but not mutable client state.

Alternative considered: extend the current yfinance REST provider class. This would combine
unrelated lifecycle and locking models, make deterministic shutdown harder, and couple stream
replacement to quote and candle REST behavior.

### Maintain one lazy connection with provider-symbol reference counts

The first YFINANCE quote or candle interest will create the SDK client, subscribe its provider
symbol, and start one listener task. Additional interests reuse that client. A provider symbol
remains subscribed while any quote interest or candle timeframe references it and is unsubscribed
only when its final reference is removed. The connection closes when no YFINANCE interests remain.

Application startup will construct only the adapter object. It will not instantiate the SDK client,
open a connection, subscribe a symbol, or start a background task.

Alternative considered: one SDK WebSocket per canonical symbol. A shared connection better matches
the SDK's multi-symbol API, existing Twelve Data architecture, and process-local subscription
sharing requirements.

### Normalize only valid price ticks

The adapter will accept a decoded mapping only when:

- `id` exactly identifies an actively subscribed approved provider symbol;
- `price` is a finite numeric value greater than zero;
- `time`, when present, parses as a non-negative Unix timestamp in milliseconds or seconds.

Accepted values use `Decimal(str(value))`. `received_at` is gateway UTC time and provider time is
retained internally when valid. Malformed, unknown, or non-price payloads are dropped without cache
updates or downstream exposure.

Yahoo's `day_volume` is cumulative session metadata rather than tick volume. It will not be copied
into quotes or derived candles.

### Derive candles from accepted ticks with zero volume

For every active candle timeframe on the tick's canonical symbol, bucket the provider timestamp, or
gateway receive time when provider time is absent, onto the existing UTC timeframe grid. The first
tick creates a forming candle; later ticks update high, low, and close; a tick in a later bucket
emits the prior candle as complete before emitting the new forming candle. Skipped buckets are not
synthesized and all derived candle volume is `Decimal("0")`.

The implementation should extract or reuse a provider-owned generic price-tick candle builder so
YFINANCE and Twelve Data retain identical bucketing, completion, validation, and session-filtering
semantics. Existing Twelve Data behavior must remain unchanged.

Alternative considered: periodically call yfinance historical APIs to create stream candles. That
would turn the stream path into polling, introduce REST latency and rate load, and violate the
selected no-fallback scope.

### Treat successful subscription without ticks as `CONNECTING`

An SDK `subscribe` call that succeeds establishes the upstream interest even if Yahoo never emits
a usable tick for that symbol. Existing `StreamManager` behavior keeps interests with no first event
in `CONNECTING`; the adapter will not manufacture an error, stale event, quote, or candle solely
because a symbol is silent.

After an interest has emitted valid data, the existing freshness monitor can transition it to
`STALE` when updates stop. No inactivity watchdog will reconnect a never-active symbol because
silence cannot be distinguished from unsupported or closed-market Yahoo behavior without adding
provider-specific assumptions.

### Supervise explicit listener failures outside the SDK

The adapter will own a listener supervisor task. If `listen()` raises or returns while interests
remain, the adapter will:

1. emit `RECONNECTING` for active interests;
2. close and discard the failed SDK client;
3. wait `PROVIDER_WS_RECONNECT_DELAY_SECONDS`;
4. create a fresh `AsyncWebSocket`;
5. resubscribe the current provider-symbol set; and
6. resume listening.

Cancellation and final close will stop the supervisor without reconnecting. An unrecoverable setup
or repeated operation failure that crosses the adapter boundary will use the existing sanitized
provider-unavailable behavior.

The SDK may internally consume some connection errors instead of returning from `listen()`. The
adapter will not inspect private connection fields or implement direct Yahoo protocol handling;
such cases remain observable through normal stream freshness state.

Alternative considered: rely entirely on the SDK's internal reconnect loop. External supervision
provides deterministic task ownership and fresh-client reconstruction when failures are visible,
while avoiding dependency on private SDK state.

## Risks / Trade-offs

- Yahoo may accept a subscription but emit no data for a futures or index symbol -> Keep the
  interest in `CONNECTING`; document that upstream event coverage is not guaranteed.
- SDK internal reconnect behavior may hide a broken connection from the supervisor -> Use
  freshness status after prior data and recreate the client whenever `listen()` terminates; avoid
  private SDK fields.
- A shared connection is a failure domain for all YFINANCE symbols -> Emit affected provider
  signals for all active YFINANCE interests and keep Binance/Twelve Data routing isolated.
- Tick-derived candles can differ from REST historical candles and have no true interval volume ->
  Use zero volume, do not synthesize gaps, and leave REST candles authoritative for backfill.
- Exact futures and index sessions are not modeled -> Do not claim `MARKET_CLOSED` for these assets
  in this change; silent never-active interests remain `CONNECTING`.
- Event bursts can fill the bounded provider queue -> Preserve non-blocking queue writes and log
  sanitized drops consistently with existing adapters.
- yfinance is unofficial and Yahoo usage terms may restrict production deployment -> Retain the
  existing research/educational-use warning and require deployment approval outside this change.

## Migration Plan

1. Add the injectable yfinance asynchronous stream adapter and price-tick normalization.
2. Reuse or extract the shared tick candle builder without changing Twelve Data behavior.
3. Register the adapter under `YFINANCE` in FastAPI lifespan and preserve lazy startup.
4. Update router, lifecycle, adapter, manager, API, and dependency-boundary tests.
5. Update product, API contract, system design, asset, and technology documentation.
6. Run focused and full tests, lint, formatting, type checks, and strict OpenSpec validation.
7. Perform an optional live smoke test that verifies connection and subscription mechanics without
   requiring every approved symbol to emit a tick.

Rollback removes the YFINANCE stream provider registration and adapter. Existing registry rows,
REST quote/candle support, and persisted historical candles remain valid.

## Open Questions

- Production observation may justify provider-specific market-session policies in a later change.
- A later provider-capability model may allow quote, candle, and stream providers to differ for one
  canonical asset without changing the public WebSocket contract.
