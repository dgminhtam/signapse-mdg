## Why

Signapse now supports Forex symbols through Twelve Data REST quotes and candles, but `/v1/stream`
still opens only Binance-backed crypto streams. Adding Forex streaming closes the final realtime
gap for the current Forex catalog and creates a reusable foundation for market-session-aware
streaming across future asset classes.

Twelve Data's WebSocket surface provides realtime price quotes rather than upstream candle events.
Therefore the gateway must normalize Forex quotes directly and derive Forex candle events from
price ticks while preserving the existing provider-agnostic public stream contract.

## What Changes

- Route `/v1/stream` subscriptions by persisted provider mapping so one downstream subscription
  can include Binance crypto and Twelve Data Forex symbols.
- Add a Twelve Data Forex WebSocket adapter behind the provider boundary using the official
  `twelvedata` SDK.
- Keep at most one process-local Twelve Data upstream WebSocket connection and share dynamic
  provider-symbol subscriptions across downstream clients.
- Normalize Twelve Data price events into existing public `quote` events.
- Build Forex candle events from Twelve Data price ticks for supported timeframes, using price
  ticks for OHLC and decimal zero as the unavailable-volume placeholder.
- Apply the existing Forex weekly quote-session policy to generated Forex candle events.
- Add a provider-agnostic `MARKET_CLOSED` stream status so closed Forex candle channels do not look
  stale or broken.
- Keep public quote/candle event shapes unchanged; add only the new status state.
- Keep REST quote/candle behavior unchanged.
- Do not implement holiday calendars, early closes, late opens, multi-replica stream coordination,
  or Twelve Data non-Forex streaming in this scope.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `market-data-websocket-stream`: route stream interests across Binance and Twelve Data, support
  Forex quote streams, derive Forex candle streams, and expose `MARKET_CLOSED` status.
- `historical-candles`: ensure streamed Forex candles that feed current cache and completed-candle
  persistence follow the existing Forex market-session eligibility rules.

## Impact

- Affects `app/domain/streams.py`, stream settings, FastAPI lifespan wiring, stream manager/provider
  orchestration, and provider adapters under `app/providers/`.
- Adds a Twelve Data Forex stream adapter and likely a small multi-provider stream router/aggregator.
- Adds Forex candle-building logic from price ticks with tests for timeframe bucketing,
  completion, zero-volume serialization, and market-session boundaries.
- Requires tests for mixed crypto/Forex downstream subscriptions, one shared Twelve Data upstream
  connection, provider failure isolation, `MARKET_CLOSED` status events, shutdown cleanup, and
  unchanged Binance behavior.
- Updates `docs/spec.md`, `docs/system-design.md`, `docs/tech-stack.md`, README stream examples,
  and OpenSpec specs.
