## Context

`GET /v1/historical-price` currently floors `at` to a one-minute bucket and asks the candle service for exactly that half-open range. When the requested instant falls inside a closed market session, the historical candle flow returns no eligible candle and the endpoint returns `PRICE_NOT_FOUND`, even though the prior eligible candle close is the useful historical price.

The candle service already supports backward count mode for "latest eligible candle opens at or before a boundary", including market-session skips and provider gap fills.

## Goals / Non-Goals

**Goals:**

- Return a historical price for past instants when at least one eligible `1m` candle exists at or before `at`.
- Preserve the existing response shape and error envelope.
- Reuse candle service market-session and provider behavior.

**Non-Goals:**

- Add response fields for lookup policy, source, timeframe, provider, or stale metadata.
- Add a provider-specific retry or paging loop to force a result through natural provider gaps.
- Change `/v1/candles` behavior.

## Decisions

- Use the existing `CandleRequest(..., limit=1, count_direction="backward")` path from `HistoricalPriceService`.
  - Rationale: it already derives eligible opens across weekends, holidays, and maintenance breaks.
  - Alternative: add a historical-price-specific repository/provider search loop. Rejected because it duplicates schedule and gap logic.

- Use the exclusive upper boundary `floor(at) + 1 minute`.
  - Rationale: this includes the candle containing `at` when it is eligible, and otherwise lets count mode walk back to the previous eligible candle.
  - Alternative: use `floor(at)` as the boundary. Rejected because it would skip an eligible candle containing the requested instant.

- Keep `PRICE_NOT_FOUND` when the backward count result is empty.
  - Rationale: provider history limits or natural provider omissions can still mean no usable historical price exists.
  - Alternative: loop backward until a candle is found. Rejected until there is a real requirement for deeper backoff, because providers can return sparse data and unbounded search is operationally risky.

## Risks / Trade-offs

- Natural provider gaps can still return `PRICE_NOT_FOUND` even if an older candle exists further back. Mitigation: keep the first implementation bounded to one existing count request; add bounded backoff later if observed.
- `pricedAt` may be much earlier than `at` across long closures or provider gaps. Mitigation: keep `pricedAt` explicit in the response and update docs/tests.
