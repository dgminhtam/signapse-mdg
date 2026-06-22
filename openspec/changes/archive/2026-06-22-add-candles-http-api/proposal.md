## Why

The gateway does not yet expose the historical candle API promised by the product contract, so
consumers cannot retrieve normalized OHLCV data or benefit from the planned PostgreSQL candle
cache. Adding the endpoint now also lets us establish a minimal provider-agnostic response before
clients depend on Binance-specific metadata.

## What Changes

- Add `GET /v1/candles` for one supported canonical symbol, timeframe, and UTC time range.
- Support the initial public timeframes `1m`, `5m`, `15m`, `1h`, and `1d` with explicit Binance
  interval mappings kept inside the gateway.
- Return normalized candles with decimal-string OHLCV values, UTC timestamps, completion state,
  and deterministic open-time ordering.
- Expose only canonical request context in the successful response: `symbol`, `timeframe`, `from`,
  `to`, and `candles`.
- Do not expose `assetClass`, `provider`, or `providerSymbol`; those values remain internal for
  registry lookup, persistence identity, provider routing, and diagnostics.
- Validate required parameters, supported symbols and timeframes, UTC range ordering and
  alignment, configured maximum range, and maximum candle count using stable `400` error codes.
- Add PostgreSQL persistence and repository-first lookup for closed candles, fetching only missing
  ranges through the official Binance Spot SDK and upserting newly fetched closed candles.
- Allow a current forming candle in the response with `complete=false`, but do not persist it as an
  authoritative closed candle.
- Add unit, route, provider-adapter, migration, and PostgreSQL integration coverage for the
  capability.

## Capabilities

### New Capabilities

- `historical-candles`: Defines the `/v1/candles` request and minimal response contract, validation,
  timeframe mapping, provider fill, persistence, completion, and error behavior.

### Modified Capabilities

None.

## Impact

- Adds candle domain models, timeframe definitions, service orchestration, API route and DTOs,
  Binance kline adapter behavior, SQLAlchemy persistence, repository methods, and an Alembic
  migration.
- Adds candle range and count settings to typed configuration and environment documentation.
- Registers the new route and stable candle request error handling in the FastAPI application.
- Uses the existing locked `binance-sdk-spot` dependency; no new runtime dependency is required.
- Requires updates to `docs/spec.md`, `docs/system-design.md`, `.env.example`, and `README.md` so
  the documented candle response no longer contains provider-specific metadata.
