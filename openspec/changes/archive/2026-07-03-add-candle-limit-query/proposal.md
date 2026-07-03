## Why

Clients need to request the latest N candles without manually calculating a time range. Twelve Data
can request by `outputsize`, but the gateway filters candles through its own calendar/session rules,
so provider count cannot be treated as the gateway's final eligible candle count.

## What Changes

- Add an optional `limit` query mode to `GET /v1/candles`.
- Make `from` and `limit` mutually exclusive; range mode keeps the current `from`/`to` behavior.
- In limit mode, derive the latest N eligible candle opens by walking the existing candle schedule
  backward from `to` or request-time UTC.
- Reuse the current persistence, cache merge, provider gap-fill, and market-session filtering flow.
- Do not guarantee exactly N returned rows when providers have natural data gaps; return up to N
  valid eligible candles.
- Do not add provider-specific paging or retry loops around Twelve Data `outputsize`.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `historical-candles`: add count-based candle request semantics alongside existing range-based
  semantics.

## Impact

- Affected API: `GET /v1/candles` accepts `limit` as an alternative to `from`.
- Affected code: candle request parsing, candle schedule helpers, candle service, route tests, and
  historical candle specs.
- Affected providers: no provider contract change; existing `limit` parameter remains a fetch
  safety cap, not the source of truth for gateway count semantics.
