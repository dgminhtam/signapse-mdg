## 1. Request and Service Logic

- [x] 1.1 Add a historical-price request parser that validates `symbol` and UTC `at`.
- [x] 1.2 Implement one-minute bucket resolution by flooring `at` to the minute and deriving `[pricedAt, pricedAt + 1m)`.
- [x] 1.3 Implement historical-price lookup by reusing `CandleService` with timeframe `1m`.
- [x] 1.4 Map an empty candle result to `PRICE_NOT_FOUND`.

## 2. HTTP API

- [x] 2.1 Add `GET /v1/historical-price` with response fields `symbol`, `price`, and `pricedAt`.
- [x] 2.2 Wire the route into FastAPI application startup.
- [x] 2.3 Add `PRICE_NOT_FOUND` to stable API error mapping with HTTP `404`.

## 3. Tests

- [x] 3.1 Cover request parsing for valid UTC `at`, missing/malformed `at`, and missing symbol.
- [x] 3.2 Cover minute flooring and one-minute candle range passed to the candle service.
- [x] 3.3 Cover successful response shape and decimal string serialization.
- [x] 3.4 Cover `UNSUPPORTED_SYMBOL`, `PRICE_NOT_FOUND`, `DATABASE_UNAVAILABLE`, and `PROVIDER_UNAVAILABLE` behavior.
- [x] 3.5 Cover that no public `timeframe` field or query requirement is exposed.

## 4. Documentation and Validation

- [x] 4.1 Update `docs/spec.md` with the historical-price contract.
- [x] 4.2 Run `openspec.cmd validate add-historical-price-api --strict`.
- [x] 4.3 Run focused pytest coverage for historical-price route and service behavior.
