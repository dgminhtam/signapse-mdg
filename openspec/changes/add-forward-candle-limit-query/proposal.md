## Why

Clients need to request N eligible candles after a known historical instant without calculating the
matching `to` boundary. The existing count mode only walks backward, so `from+limit` requests cannot
express "give me the next N candles from this point".

## What Changes

- Extend `GET /v1/candles` count mode to support `from+limit` as forward count mode.
- Preserve `to+limit` and `limit`-only as backward/latest count modes.
- Preserve `from+to` without `limit` as explicit range mode.
- Reject `from+to+limit` as ambiguous instead of treating `limit` as an ignored or slicing
  parameter.
- Reuse the gateway schedule, market-session policy, persistence lookup, provider fill, cache merge,
  and response shape.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `historical-candles`: extend count-based candle request semantics to support forward count from
  `from` and clarify invalid mixed range/count parameters.

## Impact

- Affected API: `GET /v1/candles` accepts `from+limit` for forward count and rejects
  `from+to+limit`.
- Affected code: candle request parsing, candle schedule helpers, candle service, route tests, and
  historical candle specs.
- Affected providers: no provider contract change; provider `limit` remains only a bounded fetch
  safety cap.
