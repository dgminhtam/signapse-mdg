## Why

The current market-data WebSocket requires a `timeframe` and combines live quotes with derived
candle events. This makes a pure real-time price consumer provide an irrelevant interval, and it
causes requests such as `timeframe=1w` to fail even though weekly candles are supported by the
HTTP candle API. The WebSocket candle pipeline also duplicates responsibilities that are better
served by the existing candle endpoint.

This change separates the contracts: the WebSocket becomes a quote-only stream, while
`GET /v1/candles` remains the self-contained source for completed and forming candle snapshots.
The gateway and Java client will migrate together in one coordinated breaking release.

## What Changes

- **BREAKING** Change `WS /v1/stream` to require only `symbols` and accept an optional request-wide
  `provider`; a supplied `timeframe` query is rejected with WebSocket close `1008` and reason
  `TIMEFRAME_NOT_ALLOWED`.
- **BREAKING** Emit only normalized quote events and quote lifecycle status events from the
  WebSocket. Status events use `channels: ["quote"]`; candle events, candle interests, candle
  aggregation, candle persistence, and candle-specific market-session lifecycle are removed from
  the WebSocket flow.
- Preserve the existing quote event shape, status shape and lifecycle states, provider-selection
  semantics, multi-symbol behavior, quote-cache refresh, and sanitized unrecoverable-provider
  error behavior.
- Keep `GET /v1/candles` as the only candle snapshot API. It must independently return the latest
  eligible candle for `limit=1`, including a forming candle with `complete=false` when available,
  without an active WebSocket subscription.
- Add a short-lived process-local forming-candle snapshot cache with a configurable default TTL of
  five seconds. Isolate entries by canonical symbol, Provider Selection, and timeframe; use
  per-key single-flight loading; evict an entry once its close time passes; and return
  `PROVIDER_UNAVAILABLE` as HTTP `503` when an expired entry cannot be refreshed.
- Do not add polling-rate rejection or a new endpoint, and keep the public candle response shape
  unchanged.
- Update gateway documentation, OpenSpec requirements, tests, and the Java client contract in the
  coordinated release.

## Capabilities

### New Capabilities

- None. The change redefines the existing WebSocket and candle capabilities.

### Modified Capabilities

- `market-data-websocket-stream`: make the public stream quote-only and remove all WebSocket candle
  subscription, derivation, lifecycle, and persistence requirements.
- `historical-candles`: make latest/forming candle snapshots independent of WebSocket activity and
  define the forming-snapshot cache, TTL, single-flight, expiry, and failure behavior.
- `request-provider-selection`: retain request-wide Provider Override and immutable selection while
  aligning the supported market-data surface with quote-only WebSocket delivery and REST candle
  snapshots.

## Impact

- Affects `app/api/routes_stream.py`, stream registration/fanout and provider adapters, candle
  service/cache/provider integration, typed settings, and their unit/integration tests.
- Removes WebSocket candle interests and their derived-candle cache/persistence handoff, while
  retaining REST candle provider access, PostgreSQL reuse, and completed-candle persistence.
- Changes the public WebSocket contract and requires a same-release Java client update; no
  compatibility window or feature flag is planned.
- Updates `docs/spec.md`, `docs/system-design.md`, the relevant OpenSpec specifications, and the
  deployment environment documentation. No new external dependency or shared cache is required.
