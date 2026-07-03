## Context

The gateway already has a provider-agnostic candle service: it resolves an enabled canonical
symbol, reads persisted complete candles, calculates missing expected opens, delegates missing
ranges to a provider router, normalizes fetched candles, and upserts complete rows into PostgreSQL.
`YFINANCE` symbols are seeded and quote-enabled, but the candle provider router currently only wires
`BINANCE_SPOT` and configured `TWELVE_DATA`.

The locked yfinance dependency is already isolated in `app/providers/yfinance_market_data.py` for
latest quotes. yfinance is synchronous and wraps Yahoo Finance APIs. Its public `download` function
supports the gateway's required intervals, explicit start/end boundaries, timeout, and optional
session. The yfinance documentation states that `start` is inclusive and `end` is exclusive, which
matches the gateway's candle range contract.

## Goals / Non-Goals

**Goals:**

- Serve the existing `YFINANCE` registry symbols through `GET /v1/candles`.
- Reuse the existing candle service, repository, response DTOs, and provider router contracts.
- Keep yfinance imports, sessions, DataFrame handling, and exceptions inside `app/providers/`.
- Normalize yfinance OHLCV rows into `Candle` values using `Decimal`, UTC datetimes, and the
  existing complete-candle persistence policy.
- Preserve natural Yahoo/yfinance gaps without fabricating candles.
- Keep synchronous yfinance calls off the ASGI event loop and serialized around the shared
  provider session.

**Non-Goals:**

- No yfinance WebSocket or realtime candle streaming.
- No new public candle response fields or provider metadata exposure.
- No database schema or registry migration; the target symbols already exist.
- No automatic fallback from yfinance to another provider.
- No exact exchange holiday calendar modeling for the yfinance symbols.

## Decisions

1. Use `yfinance.download` for historical candles.

   `download` exposes the controls the gateway needs directly: `tickers`, `start`, `end`,
   `interval`, `timeout`, `session`, `threads`, `progress`, and `multi_level_index`. For each
   provider fill, the adapter will call it for one provider symbol with `threads=False`,
   `progress=False`, `actions=False`, `auto_adjust=False`, and `multi_level_index=False`.

   Alternative considered: `Ticker.history`. That is also a public yfinance API, but the generated
   docs surface only `*args, **kwargs`, while `download` documents the boundary and timeout knobs
   needed for a stable adapter contract.

2. Keep yfinance candle support in the existing yfinance provider module.

   The quote provider already owns the yfinance session factory, allowlist, timeout patching, and
   serialization lock. Extending the module to expose a market-data provider that implements both
   `fetch_latest_prices` and `fetch_candles` avoids a second yfinance session boundary and keeps
   dependency tests simple.

   Alternative considered: a separate `yfinance_candles.py` adapter. That would reduce file size,
   but it risks duplicate allowlists, duplicate session setup, and divergent error handling.

3. Preserve the existing provider router behavior.

   The application candle provider map will add `"YFINANCE"` unconditionally because yfinance does
   not require user-provided credentials. Unsupported provider symbols remain blocked by the
   adapter allowlist; unsupported providers still raise `ProviderUnavailableError` without fallback.

   Alternative considered: feature-flag yfinance candle support. That adds configuration surface
   without a clear deployment need because the dependency and registry rows are already present.

4. Normalize DataFrame rows defensively.

   The adapter will require OHLC values to be present, finite, positive decimals, with
   `high >= max(open, close)` and `low <= min(open, close)`. Volume will use a finite non-negative
   decimal when present and exact `Decimal("0")` when yfinance omits or nulls it, matching the
   existing non-null public candle contract. Duplicate open timestamps or malformed indexes raise
   the sanitized provider-unavailable boundary.

   Alternative considered: pass through rows with missing volume as provider failures. That is too
   brittle for index symbols, where volume can be absent or not meaningful.

5. Treat provider timestamps as authoritative.

   The adapter will convert yfinance row indexes to UTC, filter to `start <= open_time < end`, and
   derive `close_time` from the requested timeframe duration. It will not shift provider timestamps
   to an assumed universal grid. Existing service-level market-session filtering still applies; no
   additional exact holiday or maintenance-session model is introduced in this change.

   Alternative considered: add detailed per-futures-market sessions before enabling candles. That
   is larger than the current goal and can be layered later without changing the public API.

## Risks / Trade-offs

- yfinance/Yahoo may return partial or empty data for some symbols or intraday ranges -> The
  adapter preserves valid rows, returns empty lists for no rows, and maps operational failures to
  `PROVIDER_UNAVAILABLE`.
- Intraday history availability can be limited by Yahoo beyond the gateway's generic max range ->
  Keep existing request validation and treat provider-side range limits as provider availability
  behavior unless a later product decision adds symbol/timeframe-specific limits.
- Commodity futures and index trading sessions are not modeled exactly -> Provider-returned gaps
  are preserved and not synthesized; future changes can add market-session policies per symbol.
- yfinance is synchronous and may mutate shared session/cache state -> Calls run in
  `asyncio.to_thread` under the existing adapter lock.
- yfinance DataFrame shapes can vary for empty, single-symbol, or multi-index returns -> Force
  single-symbol options where possible and cover DataFrame normalization with fake DataFrame tests.

## Migration Plan

1. Implement the yfinance candle adapter and wire it into the existing candle provider router.
2. Add unit coverage for interval mapping, timeout/session use, DataFrame normalization, invalid
   payload rejection, no-data behavior, and serialization under concurrent calls.
3. Add route/service tests proving `YFINANCE` symbols use `/v1/candles`, reuse persisted rows, and
   fail independently from Binance and Twelve Data.
4. Update docs to move `YFINANCE` symbols from quote-only to quote-and-candle support while keeping
   WebSocket out of scope.
5. Deploy with no schema migration. Rollback is code-only: remove the `YFINANCE` candle provider
   wiring; persisted yfinance candle rows can remain harmlessly unused.

## Open Questions

- Should a follow-up add precise per-symbol futures/index market sessions to reduce repeated fills
  for known closed periods?
- Should daily yfinance candles be documented as Yahoo exchange-local sessions normalized to UTC
  labels, or should the gateway later add display metadata for exchange dates?
