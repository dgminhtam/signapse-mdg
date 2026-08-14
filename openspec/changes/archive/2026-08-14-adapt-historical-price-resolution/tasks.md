## 1. Historical-price contract and resolver

- [x] 1.1 Extend `HistoricalPriceResult` and the HTTP response DTO with canonical `resolution` while preserving internal display-precision formatting and the exact four-field public shape.
- [x] 1.2 Add request-time validation that captures one UTC `now` and rejects `at > now` with `INVALID_TIME_RANGE` before registry, persistence, or provider work.
- [x] 1.3 Replace the one-minute-only policy in `HistoricalPriceService` with the fixed sequential ladder `1m`, `5m`, `1h`, `1d`, resolving Provider Selection once and reusing it for every attempt.
- [x] 1.4 Select only complete candles with `close_time <= at`, return the selected candle's open time as `pricedAt`, stop on the first eligible result, and preserve `PRICE_NOT_FOUND` when all four attempts are empty.
- [x] 1.5 Preserve operational provider exceptions as `PROVIDER_UNAVAILABLE` without trying a coarser timeframe or another provider mapping.

## 2. Provider and candle-flow compatibility

- [x] 2.1 Audit and update canonical-to-native timeframe mappings for every supported candle provider so the shared ladder can request `1m`, `5m`, `1h`, and `1d` without introducing provider-specific public values.
- [x] 2.2 Ensure valid empty/no-data responses, including retention limits, natural gaps, and closed sessions, normalize to `[]`; keep timeout, transport, authentication, quota/rate-limit, malformed-payload, and invalid-response paths as `ProviderUnavailableError`.
- [x] 2.3 Verify every resolution attempt continues through the existing `CandleService` persistence, cache, normalization, and market-session flow, storing coarse candles under their actual timeframe rather than relabeling or synthesizing them.
- [x] 2.4 Verify an explicit provider override and the default Provider Selection remain immutable across all resolution attempts, with no cross-provider fallback.

## 3. Automated coverage

- [x] 3.1 Update historical-price service tests for finest-resolution success, empty fallback ordering, coarser selection, no-lookahead, forming-candle exclusion, closed-session behavior, four-attempt bound, provider immutability, operational stop, and future-time rejection.
- [x] 3.2 Update API tests for the exact `symbol`/`price`/`pricedAt`/`resolution` response, canonical resolution values, decimal display formatting, future `INVALID_TIME_RANGE`, and sanitized stable error responses.
- [x] 3.3 Add or update provider tests for valid no-data versus operational failures across each supported provider, including the relevant yfinance retention/no-data cases.
- [x] 3.4 Add integration coverage proving coarse fallback reuses persistence/cache and preserves the selected provider and actual candle timeframe.

## 4. Documentation and verification

- [x] 4.1 Update `docs/spec.md`, `docs/system-design.md`, and provider-support documentation with the fixed ladder, completed-candle/no-lookahead rule, future-time validation, response `resolution`, and no cross-provider fallback.
- [x] 4.2 Run the focused historical-price/provider tests, the full `uv run pytest` suite, `uv run ruff check .`, and `uv run mypy app`; resolve regressions without changing the agreed contract.
