## 1. Quote-only WebSocket contract

- [x] 1.1 Update the stream request model/parser so `symbols` and optional request-wide `provider`
  remain supported, `timeframe` is removed from the internal request, and any present timeframe
  query closes with `TIMEFRAME_NOT_ALLOWED` before registry/provider access.
- [x] 1.2 Preserve CSV symbol canonicalization, first-occurrence deduplication, symbol limits,
  Provider Override validation, and all-or-nothing symbol/Provider Selection resolution.
- [x] 1.3 Update the WebSocket route to detect every `timeframe` query presence, return close `1008`
  with the exact reason, and log request ID, symbols, submitted timeframe, operation, and error
  code without unsafe details.
- [x] 1.4 Update stream event serialization and status construction so quote events keep their
  exact shape and status events always use `channels: ["quote"]` without `MARKET_CLOSED`.

## 2. Quote stream manager and provider adapters

- [x] 2.1 Remove `CandleInterest` registration, timeframe-bearing stream keys, candle event
  dispatch, derived-candle state, candle cache writes, candle persistence handoff, and candle
  session checks from `StreamManager`.
- [x] 2.2 Preserve quote reference counting, bounded per-client fanout, disconnect cleanup, idle
  grace, application-lifecycle ownership, and Provider Selection isolation for quote interests.
- [x] 2.3 Implement quote lifecycle transitions: `CONNECTING` at registration, `SUBSCRIBED` after
  the first valid quote, quote-only `STALE`, recovery to `SUBSCRIBED`, `RECONNECTING`, and
  sanitized `ERROR`/`1011` shutdown.
- [x] 2.4 Ensure every valid normalized provider quote updates `QuoteCache` before fanout and that
  the WebSocket never sends an initial quote snapshot.
- [x] 2.5 Remove WebSocket kline subscriptions and tick-to-candle aggregation from Binance,
  Twelve Data, yfinance, WTI, ETF, and crypto stream adapters while retaining their REST candle
  provider implementations.
- [x] 2.6 Remove obsolete stream candle persistence configuration/dependencies and update lifespan
  construction so only quote stream resources are owned and cleaned up.

## 3. Forming candle snapshot cache

- [x] 3.1 Add a process-local forming snapshot cache entry/key model containing canonical symbol,
  Provider Selection/provider symbol, timeframe, normalized candle, and gateway store time.
- [x] 3.2 Add typed `CANDLE_FORMING_CACHE_TTL_SECONDS` configuration with a validated default of
  five seconds and wire one process-local cache instance into the candle service.
- [x] 3.3 Implement exact-key cache isolation across canonical symbol, provider, provider symbol,
  and timeframe; do not share forming snapshots across Provider Selections.
- [x] 3.4 Implement per-key single-flight loading with a double-check after lock acquisition so
  concurrent same-key misses make at most one provider request while unrelated keys remain
  independent.
- [x] 3.5 Evict forming snapshots when TTL expires or current time reaches `closeTime`; never
  relabel an expired forming snapshot as complete and never serve it after refresh failure.

## 4. Self-contained REST candle behavior

- [x] 4.1 Update `CandleService` so REST provider fills classify candles using the captured gateway
  clock, persist only eligible completed candles, and store eligible incomplete candles in the
  forming snapshot cache.
- [x] 4.2 Make `GET /v1/candles` consult the forming snapshot cache independently of WebSocket
  activity, while preserving PostgreSQL reads, provider gap fills, session filtering, and exact
  provider-selection identity.
- [x] 4.3 Implement `limit=1` latest semantics: return a fresh forming candle when available,
  otherwise the latest completed candle, and `candles: []` when no eligible candle exists.
- [x] 4.4 Return HTTP `503` with `PROVIDER_UNAVAILABLE` when an expired forming snapshot cannot be
  refreshed; do not return stale forming data and do not introduce a `429` polling response.
- [x] 4.5 Preserve the existing candle response fields, decimal/timestamp serialization, range and
  count validation, and completed-candle persistence behavior.

## 5. Documentation and coordinated client release

- [x] 5.1 Update `docs/spec.md` with the quote-only WebSocket URL/query contract, rejection reason,
  quote-only lifecycle, removed candle events, and REST forming/latest candle behavior.
- [x] 5.2 Update `docs/system-design.md`, `docs/tech-stack.md`, and `.env.example` for removed
  stream candle plumbing and the forming snapshot TTL setting.
- [x] 5.3 Update the Java client in its coordinated release package to omit `timeframe` from quote
  stream URLs, consume quote-only status/events, and call `GET /v1/candles` for candle snapshots.
- [x] 5.4 Record release and rollback notes confirming gateway and Java client must deploy together
  with no mixed-version compatibility window.

## 6. Verification

- [x] 6.1 Add WebSocket boundary tests for valid no-timeframe subscriptions, empty/valid/unsupported
  timeframe rejection with exact `1008/TIMEFRAME_NOT_ALLOWED`, safe rejection logging, symbols,
  deduplication, limits, and Provider Override behavior.
- [x] 6.2 Add quote stream integration tests for quote-only events/status channels, first-quote
  subscription, stale/recovery/reconnect/error lifecycle, quote-cache updates, no initial snapshot,
  and absence of candle provider subscriptions/events/persistence.
- [x] 6.3 Add provider adapter tests proving ticker-only upstream behavior and quote normalization
  for Binance, Twelve Data, yfinance, WTI, ETF, and crypto mappings.
- [x] 6.4 Add forming-cache tests for five-second TTL, configured TTL, provider/timeframe key
  isolation, close-time eviction, per-key single-flight, cache hits without `429`, and expired
  refresh failures without stale responses.
- [x] 6.5 Add public candle HTTP/service tests for no active WebSocket dependency, `limit=1` forming
  versus completed selection, empty results, unchanged response shape, completed persistence, and
  sanitized `503 PROVIDER_UNAVAILABLE` behavior.
- [x] 6.6 Run the targeted stream/candle tests, the full pytest suite, Ruff, mypy, and OpenSpec
  validation; resolve regressions before marking the change ready for implementation review.
