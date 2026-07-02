## Context

`GET /v1/candles` currently requires a UTC `[from,to)` range. After symbol resolution, the candle
service builds eligible expected opens from the symbol schedule and market-session policy, then
reuses persistence, cache, provider gap fill, and normalization.

Twelve Data accepts `outputsize`, but that count is provider-side raw data. The gateway can still
discard rows by inline calendar config, Forex/XAU session rules, range bounds, duplicate checks, and
natural provider gaps.

## Goals / Non-Goals

**Goals:**

- Let clients request the latest N eligible candles without calculating `from`.
- Use the gateway's schedule and market-session policy as the source of truth for count semantics.
- Reuse the existing range fill path after deriving expected opens.
- Preserve current response shape and provider interfaces.

**Non-Goals:**

- Do not guarantee exactly N returned candles when providers omit natural market data.
- Do not add provider-specific pagination, retry loops, or backtracking fetches.
- Do not change stream behavior, persistence schema, or public candle response fields.

## Decisions

- Add `limit` as an alternative request mode.
  - Alternative considered: add a separate endpoint such as `/v1/candles/latest`.
  - Rationale: the response shape and service flow are the same; a query parameter is the smallest
    contract change.
- Make `from` and `limit` mutually exclusive.
  - Alternative considered: allow both and treat `limit` as a response slice.
  - Rationale: slicing after a user-supplied range creates ambiguous provider-fill behavior and can
    hide missing eligible slots.
- Resolve the symbol before count-mode range derivation.
  - Alternative considered: derive a conservative time range before symbol lookup.
  - Rationale: calendar eligibility depends on the persisted symbol config and provider schedule.
- Add a schedule helper that walks backward from `to` and collects N eligible opens.
  - Alternative considered: call Twelve Data with `outputsize=N`.
  - Rationale: provider raw count can disagree with gateway calendar filtering.
- Keep provider `limit` as `gap.expected_count + 1`.
  - Alternative considered: change provider calls to count-only mode.
  - Rationale: existing provider calls already fetch bounded windows and normalize by `[start,end)`.

## Risks / Trade-offs

- Sparse provider data can return fewer than N candles -> document count mode as "up to N" valid
  eligible candles.
- Walking backward across long market closures costs schedule checks -> bounded by
  `MAX_CANDLES_PER_REQUEST`; revisit only if profiling shows a problem.
- Monthly count mode needs calendar-month stepping -> reuse the existing month helpers rather than
  adding a separate calendar abstraction.
