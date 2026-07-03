## Why

The ten enabled `YFINANCE` assets already support latest quotes and historical candles, but
`/v1/stream` rejects them because no yfinance stream adapter is registered. Adding the locked
yfinance package's asynchronous WebSocket client completes provider coverage behind the existing
provider-agnostic stream contract and leaves room to replace or supplement the upstream provider
later without changing clients.

## What Changes

- Route `XAG/USD`, `BRENT`, `NATGAS`, `COFFEE`, `SUGAR`, `WHEAT`, `CORN`, `SPX`, `NDX`, and
  `DJI` stream interests through their persisted `YFINANCE` provider mappings.
- Use yfinance `AsyncWebSocket` behind a repository-owned adapter with one lazy process-local
  connection and shared provider-symbol subscriptions.
- Normalize accepted Yahoo price ticks into existing quote events and derive requested
  `1m`, `5m`, `15m`, `1h`, and `1d` candle events with zero volume.
- Manage listener, reconnect, resubscription, unsubscribe, and shutdown behavior at the adapter
  boundary while preserving sanitized provider status events.
- Keep subscriptions in `CONNECTING` when Yahoo accepts a symbol but emits no usable tick; do not
  add polling, symbol remapping, or fallback to another provider.
- Preserve the current public WebSocket URL, event schemas, close codes, registry mappings, and
  Binance/Twelve Data behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `market-data-websocket-stream`: Enabled `YFINANCE` assets become valid stream targets whose
  quote and candle interests use the shared yfinance asynchronous price stream.
- `provider-sdk-integration`: The locked yfinance dependency is used for WebSocket streaming
  through an isolated asynchronous adapter in addition to latest quotes and historical candles.

## Impact

- Affects provider stream adapters, stream provider routing, FastAPI lifespan wiring, derived
  candle handling, dependency-boundary tests, and WebSocket integration tests.
- Uses the already locked `yfinance==1.4.1` dependency and requires no new credential, database
  migration, registry change, or public API field.
- Yahoo/yfinance remains an unofficial upstream intended for research and educational use; its
  symbol event coverage is not treated as a gateway support guarantee.
