## 1. Candle Provider Routing

- [x] 1.1 Add a `CandleProvider` router that dispatches using `SupportedSymbol.provider`.
- [x] 1.2 Route `BINANCE_SPOT` symbols to the existing Binance candle adapter without changing its request behavior.
- [x] 1.3 Route `TWELVE_DATA` symbols to the existing Twelve Data Forex candle adapter.
- [x] 1.4 Map unknown, missing, or unusable provider registrations to the sanitized provider-unavailable boundary.
- [x] 1.5 Preserve repository-first reads so a fully persisted Forex range does not require a configured Twelve Data provider.

## 2. Twelve Data Candle Normalization

- [x] 2.1 Translate gateway `[from,to)` ranges into Twelve Data `start_date` and final eligible `end_date` boundaries.
- [x] 2.2 Preserve UTC, ascending order, provider interval mapping, and expected-slot `outputsize` parameters.
- [x] 2.3 Normalize omitted or null Forex volume to exact decimal zero.
- [x] 2.4 Reject malformed supplied volume, invalid OHLC values, duplicate rows, and inconsistent timestamps through `ProviderUnavailableError`.
- [x] 2.5 Exclude any provider row opening outside `[from,to)` without exposing or persisting it.
- [x] 2.6 Preserve natural missing Forex slots without synthesizing candles.
- [x] 2.7 Ensure cancelled Twelve Data candle calls propagate cancellation rather than becoming provider failures.

## 3. FastAPI Dependency Wiring

- [x] 3.1 Update candle route dependency construction to build Binance and optionally Twelve Data behind the candle provider router.
- [x] 3.2 Ensure missing `TWELVEDATA_API_KEY` does not fail application startup or Binance candle requests.
- [x] 3.3 Keep Twelve Data SDK imports and exceptions confined to `app/providers/`.
- [x] 3.4 Preserve the existing candle request and response DTOs exactly.
- [x] 3.5 Confirm no Twelve Data provider is added to the WebSocket lifespan or stream route.

## 4. Tests

- [x] 4.1 Add candle provider router tests for Binance and Twelve Data dispatch.
- [x] 4.2 Add tests for unsupported provider registration and missing Twelve Data configuration.
- [x] 4.3 Add Twelve Data adapter tests for all supported timeframe mappings and half-open range translation.
- [x] 4.4 Add Twelve Data adapter tests for absent/null volume, malformed volume, boundary rows, duplicates, and cancellation.
- [x] 4.5 Add candle service tests proving persisted Forex ranges skip provider access and missing ranges use Twelve Data.
- [x] 4.6 Add route/dependency tests for Forex candles using fake providers without live Twelve Data calls.
- [x] 4.7 Add regression tests proving Binance candle behavior and public DTO fields remain unchanged.
- [x] 4.8 Confirm existing WebSocket tests remain Binance-backed and do not instantiate Twelve Data streams.

## 5. Documentation

- [x] 5.1 Update `docs/spec.md` to describe registry-routed crypto and Forex candle fills.
- [x] 5.2 Update `docs/system-design.md` candle flow and Twelve Data adapter responsibilities.
- [x] 5.3 Update README runbook with a Forex candle example and API-key requirements.
- [x] 5.4 Document that zero Forex volume means upstream volume is unavailable, not measured zero activity.
- [x] 5.5 Remove stale documentation claiming Twelve Data is not wired to `/v1/candles`.

## 6. Verification

- [x] 6.1 Run `openspec validate add-forex-candles-http-api --strict`.
- [x] 6.2 Run Twelve Data adapter, candle router, service, route, and Binance regression unit tests.
- [x] 6.3 Run relevant candle persistence integration tests when `TEST_DATABASE_URL` is available.
- [x] 6.4 Run the complete unit test suite.
- [x] 6.5 Run `ruff check .` and `mypy app`.
