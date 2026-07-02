## Why

Clients need a small API to ask "what was the approximate price at this past UTC instant" without
knowing candle timeframes or rebuilding gateway calendar/provider logic.

## What Changes

- Add `GET /v1/historical-price` for one canonical `symbol` and one UTC `at` timestamp.
- Resolve the price from the existing smallest public candle granularity, `1m`, inside the gateway.
- Return a minimal provider-agnostic response: `symbol`, `price`, and `pricedAt`.
- Return `PRICE_NOT_FOUND` when no eligible one-minute candle can be found for the requested instant.

## Capabilities

### New Capabilities

- `historical-price`: Approximate historical price lookup by canonical symbol and UTC timestamp.

### Modified Capabilities

- None.

## Impact

- Affected API: new `GET /v1/historical-price` HTTP endpoint.
- Affected service flow: reuse the existing candle service, registry validation, provider routing,
  PostgreSQL candle cache, and decimal serialization.
- Affected docs/tests: API contract docs and route/service tests for validation, response shape,
  candle reuse, and not-found behavior.
- No new provider dependency, persistence table, raw tick storage, or public timeframe parameter.
