## Context

The gateway already serves historical candles through `GET /v1/candles` with registry lookup,
market-session filtering, PostgreSQL-first reads, provider gap fill, and decimal serialization.
It does not persist raw ticks, so an exact trade price at an arbitrary instant is not available.

## Goals / Non-Goals

**Goals:**

- Add a concise API for approximate historical price lookup by `symbol` and `at`.
- Hide timeframe selection from clients and use the existing `1m` candle granularity internally.
- Reuse the historical candle flow instead of adding provider calls, storage, or duplicate calendar
  logic.
- Keep the response small enough for Java backend consumption.

**Non-Goals:**

- Do not store raw ticks or expose tick-level semantics.
- Do not add a public `timeframe`, `source`, OHLC, provider, asset class, or freshness field.
- Do not add nearest-neighbor searches across multiple candles.
- Do not introduce new provider dependencies or persistence tables.

## Decisions

- Add `GET /v1/historical-price?symbol=...&at=...`.
  - Alternative considered: extend `/v1/candles` with a projection mode.
  - Rationale: clients want a price lookup, not candle transport; a small endpoint avoids leaking
    timeframe and candle fields.
- Always use public timeframe `1m` internally.
  - Alternative considered: accept a `timeframe` query parameter.
  - Rationale: the product asks for closest practical approximation; `1m` is the smallest existing
    supported candle interval and avoids one more public decision for clients.
- Floor `at` to the containing one-minute candle open and request `[open, open + 1m)`.
  - Alternative considered: request backward `limit=1`.
  - Rationale: containing-candle semantics are deterministic and match the phrase "at that time";
    backward lookup would answer a different "as of previous close" question.
- Return the candle `close` as `price` and the candle `openTime` as `pricedAt`.
  - Alternative considered: return `openTime`, `closeTime`, or a `source` field.
  - Rationale: `pricedAt` is enough to reveal the one-minute approximation while keeping the
    response minimal.
- Map an empty candle result to `404 PRICE_NOT_FOUND`.
  - Alternative considered: return `200` with `price: null`.
  - Rationale: current API style uses stable errors for unavailable data, and null prices make
    client handling sloppier.

## Risks / Trade-offs

- Using candle close can look ahead within the requested minute -> acceptable for display and
  approximate lookup; add a separate "as-of previous close" mode only if backtesting needs it.
- Provider gaps or market-closed windows can produce no candle -> return `PRICE_NOT_FOUND` without
  synthetic prices.
- `pricedAt` is a minute boundary, not the original `at` instant -> document that it identifies the
  one-minute bucket used for the approximation.
