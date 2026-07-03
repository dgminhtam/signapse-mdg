## 1. Adapter Implementation

- [x] 1.1 Extend `app/providers/yfinance_market_data.py` with a yfinance historical candle provider method that implements the existing `CandleProvider.fetch_candles` protocol.
- [x] 1.2 Add yfinance timeframe mapping for `1m`, `5m`, `15m`, `1h`, and `1d` using yfinance-supported intervals.
- [x] 1.3 Call `yfinance.download` for one provider symbol at a time with explicit `start`, `end`, `interval`, `timeout`, shared session, `threads=False`, `progress=False`, `actions=False`, `auto_adjust=False`, and `multi_level_index=False`.
- [x] 1.4 Keep yfinance synchronous work inside `asyncio.to_thread` and serialize access with the existing adapter lock/session boundary.
- [x] 1.5 Normalize yfinance history rows into `Candle` models with UTC open/close times, `Decimal` OHLCV values, strict OHLC validation, duplicate timestamp rejection, and exact zero volume for missing or null volume.
- [x] 1.6 Return empty candle lists for valid no-row yfinance responses while mapping malformed payloads and operational failures to `ProviderUnavailableError`.

## 2. API Wiring

- [x] 2.1 Add a cached yfinance candle provider factory in `app/api/routes_candles.py` using `PROVIDER_HTTP_TIMEOUT_SECONDS`.
- [x] 2.2 Register `"YFINANCE"` in the candle provider router without requiring provider credentials or opening yfinance sessions at application startup.
- [x] 2.3 Ensure unsupported yfinance provider symbols remain blocked by the adapter allowlist and never fall back to Binance or Twelve Data.

## 3. Tests

- [x] 3.1 Add yfinance candle adapter unit tests for interval mapping, download arguments, session/timeout use, allowlist behavior, no-data responses, and cancellation propagation.
- [x] 3.2 Add yfinance normalization tests for valid rows, UTC timestamp conversion, half-open range filtering, duplicate timestamps, invalid OHLC, malformed decimals, missing volume, and provider gaps.
- [x] 3.3 Add candle provider router tests proving `YFINANCE` routes to the yfinance adapter and unsupported provider mappings remain `ProviderUnavailableError`.
- [x] 3.4 Add `/v1/candles` route/service tests proving yfinance symbols fetch missing ranges, reuse fully persisted ranges without provider calls, preserve the public response shape, and isolate provider failures from other providers.
- [x] 3.5 Update yfinance dependency/import-boundary tests so yfinance remains confined to `app/providers/` while quote and candle routes can register provider-owned adapters.

## 4. Documentation

- [x] 4.1 Update `docs/spec.md` and `docs/api-contract.md` to mark the seeded `YFINANCE` assets as quote-and-candle supported while WebSocket remains unavailable.
- [x] 4.2 Update `docs/system-design.md`, `docs/tech-stack.md`, and `docs/assets.md` with the yfinance candle adapter, `download` usage, range semantics, volume behavior, provider-gap policy, and no-startup-session behavior.
- [x] 4.3 Preserve existing notes that yfinance is suitable for research/educational market data usage and that commodity futures/index units may need product-level interpretation.

## 5. Validation

- [x] 5.1 Run focused unit tests for the yfinance provider, candle provider router, candle API route, and import-boundary coverage.
- [x] 5.2 Run `uv run --offline pytest`, `uv run --offline ruff check .`, `uv run --offline ruff format --check .`, and `uv run --offline mypy app`.
- [x] 5.3 Run `openspec.cmd validate add-yfinance-candle-api --strict` and resolve any proposal/spec/task issues.
- [x] 5.4 Optionally run a live smoke request against representative `YFINANCE` candles when network access and yfinance upstream availability are approved.
