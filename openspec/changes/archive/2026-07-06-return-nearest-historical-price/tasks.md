## 1. Historical Price Resolution

- [x] 1.1 Update `HistoricalPriceService` to request the latest eligible `1m` candle at or before the requested instant using existing backward count mode.
- [x] 1.2 Preserve existing parse errors, service error mapping, response shape, and `PRICE_NOT_FOUND` behavior when no candle is returned.

## 2. Tests

- [x] 2.1 Update historical price service tests for containing-bucket hits and closed-session fallback to an earlier `pricedAt`.
- [x] 2.2 Keep or update API tests proving serialization and sanitized error responses remain unchanged.

## 3. Documentation

- [x] 3.1 Update `docs/spec.md` historical-price semantics to describe nearest eligible prior price and the narrower `PRICE_NOT_FOUND` case.
