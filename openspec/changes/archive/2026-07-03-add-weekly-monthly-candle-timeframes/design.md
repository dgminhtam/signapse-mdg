## Context

`GET /v1/candles` currently accepts only `1m`, `5m`, `15m`, `1h`, and `1d`.
Requests for `30m`, `1w`, or `1mo` fail during request parsing before the symbol's persisted
provider can be used. Provider adapters already own interval translation, and persistence already
keys candles by the public timeframe string, so no schema change is needed.

Monthly candles are the only non-fixed-duration case. Treating a month as 30 days would produce
wrong open/close times and gap detection around February and 31-day months.

## Goals / Non-Goals

**Goals:**

- Accept exactly `1m`, `5m`, `15m`, `30m`, `1h`, `1d`, `1w`, and `1mo` on the historical candle
  endpoint.
- Preserve exact half-open response filtering for non-aligned `from`/`to` boundaries.
- Use calendar-aware monthly open/close calculations.
- Keep provider-specific interval names inside adapters.

**Non-Goals:**

- Add aliases such as `1week`, `1month`, or provider-native interval names to the public API.
- Add weekly/monthly WebSocket subscriptions or derived realtime candles.
- Add new dependencies or change database schema.

## Decisions

- Public names are exactly `1m`, `5m`, `15m`, `30m`, `1h`, `1d`, `1w`, and `1mo`.
  Alternative: also accept long aliases such as `1week`/`1month`. Rejected because the agreed
  gateway contract is the compact eight-value set, and aliases expand validation and docs surface.

- Add `30m` and `1w` through the existing duration-based path.
  They are fixed periods, so the existing fixed schedule can handle them.

- Add a small calendar-month schedule for `1mo`.
  The schedule should find month-start opens, group missing sections by consecutive months, and
  derive close time as next calendar month minus one millisecond. This avoids pretending months
  have a fixed duration.

- Keep provider mappings in adapters.
  Twelve Data maps `1m/5m/15m/30m/1h/1d/1w/1mo` to
  `1min/5min/15min/30min/1h/1day/1week/1month`; Binance maps to
  `1m/5m/15m/30m/1h/1d/1w/1M`; yfinance maps to `1m/5m/15m/30m/1h/1d/1wk/1mo`.
  Unsupported provider mappings still raise the existing sanitized provider-unavailable boundary.

- Keep request limits count-based.
  `MAX_CANDLES_PER_REQUEST` should use exact scheduled opens for `1mo`; pre-validation may use a
  conservative upper bound before symbol resolution.

## Risks / Trade-offs

- Calendar-month math can drift if hand-rolled loosely -> keep it tiny and test February,
  month-end, and half-open boundaries.
- Some providers may label weekly/monthly candles differently -> normalize using provider open
  timestamps and filter to `[from,to)` as today.
- Public API grows by exactly three strings -> no aliases until clients need them.
