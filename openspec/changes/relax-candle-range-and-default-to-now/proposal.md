## Why

The candle endpoint currently requires both range boundaries to align to a universal UTC epoch
grid, but Twelve Data instruments can label valid hourly candles at `:30` rather than `:00`.
Requiring clients to supply an aligned `to` also makes “fetch through now” awkward and rejects the
natural current time.

## What Changes

- Make the `to` query parameter optional for `GET /v1/candles`.
- Resolve an omitted `to` to one captured request-time UTC instant and always return that resolved
  value in the response.
- Stop requiring public `from` and `to` values to align to timeframe boundaries while preserving
  timezone, ordering, elapsed-range, and maximum-candle protections.
- Treat public ranges consistently as exact half-open filters `[from, to)`.
- Introduce provider/market-aware expected candle schedules so persistence gap detection does not
  assume every provider uses the epoch-aligned `:00` grid.
- Preserve Twelve Data candle timestamps instead of shifting valid `:30` open times.
- Treat a Twelve Data “no data available for the specified dates” response as a successful empty
  provider result rather than `PROVIDER_UNAVAILABLE`.
- Keep malformed payloads, authentication failures, entitlement failures, rate limits, timeouts,
  and transport errors mapped to the existing provider-unavailable boundary.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `historical-candles`: make `to` optional, relax public alignment validation, add market-aware
  expected candle schedules, and distinguish valid empty provider ranges from provider failures.

## Impact

- Changes the public query contract for `GET /v1/candles`; existing requests with explicit aligned
  `to` remain valid.
- Affects candle request parsing, range validation, response range serialization, expected-count
  enforcement, gap detection, provider normalization, and Twelve Data error classification.
- Requires deterministic clock injection in request parser/route tests.
- Requires regression coverage across Binance epoch-aligned candles and Twelve Data Forex,
  commodity, stock, and ETF candle labels.
- Does not change candle response fields, timeframe values, persistence identity, market-session
  policies, or provider routing.
