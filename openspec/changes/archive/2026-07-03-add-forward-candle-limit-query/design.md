## Context

`add-candle-limit-query` adds backward count mode for `GET /v1/candles`: derive the latest N
eligible candle opens before `to` or request-time UTC, then reuse the existing range fill path.

Clients also need the opposite shape: start from a historical instant and ask for the next N
eligible candles. That cannot be expressed by `to+limit` without calculating the future boundary on
the client, which is exactly what gateway-side calendar filtering is meant to avoid.

## Goals / Non-Goals

**Goals:**

- Support `from+limit` as forward count mode.
- Keep `to+limit` and `limit`-only as backward/latest count modes.
- Keep `from+to` without `limit` as the existing explicit range mode.
- Reject `from+to+limit` as ambiguous.
- Reuse the same schedule, market-session policy, persistence, provider fill, and cache merge flow.

**Non-Goals:**

- Do not add a `direction` parameter or a new endpoint.
- Do not change provider interfaces or provider-side count semantics.
- Do not guarantee exactly N returned candles when providers have natural data gaps.

## Decisions

- Interpret query parameter combinations directly.
  - `from+to`: range mode.
  - `from+limit`: forward count mode.
  - `to+limit`: backward count mode.
  - `limit`: backward count mode from request-time UTC.
  - `from+to+limit`: invalid.
  - Alternative considered: add `direction=forward|backward`.
  - Rationale: `from` and `to` already express direction; an extra parameter is avoidable API
    surface.
- Add a schedule helper that walks forward from `from` and collects N eligible opens.
  - Alternative considered: derive a conservative `to` and call existing `expected_opens`.
  - Rationale: closed sessions can make a conservative window either too short or too large; walking
    eligible opens matches the existing backward count model.
- Treat the public `from` boundary as inclusive for forward count.
  - Rationale: this matches existing half-open range semantics: a candle whose open equals `from` is
    eligible.
- Resolve the forward-count response range from derived opens.
  - If eligible opens exist, response `from` is the first derived open and response `to` is the
    exclusive boundary immediately after the final derived open.
  - Rationale: response shape stays unchanged and describes the actual gateway range used for
    persistence/provider access.

## Risks / Trade-offs

- Walking forward across long closures costs schedule checks -> bound by `MAX_CANDLES_PER_REQUEST`
  and reuse the existing market-session policy.
- Monthly forward count needs calendar-month stepping -> reuse the existing month helper pattern.
- `from+to+limit` rejection may surprise clients expecting `limit` to slice -> fail fast instead of
  silently ignoring a query parameter.
