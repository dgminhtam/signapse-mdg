## Why

Historical price consumers need a usable price for any past instant when the market has already traded before that instant. The current exact one-minute bucket lookup returns `PRICE_NOT_FOUND` during closed sessions, which breaks downstream jobs even though a valid prior close exists.

## What Changes

- Change `GET /v1/historical-price` to return the nearest available eligible `1m` candle close at or before the requested `at` instant.
- Allow `pricedAt` to be earlier than the requested instant's containing one-minute bucket when the requested bucket is closed or has no returned candle.
- Keep the response shape unchanged: exactly `symbol`, `price`, and `pricedAt`.
- Keep `PRICE_NOT_FOUND` only for cases where no historical price exists before the requested instant.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `historical-price`: Change historical price resolution from exact bucket only to nearest eligible prior price.

## Impact

- Affects `app/services/historical_prices.py` and unit/API expectations for historical price lookup.
- Reuses the existing historical candle service, market-session policies, provider routing, and persistence behavior.
- No new dependencies, database changes, or public response fields.
