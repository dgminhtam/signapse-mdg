## 1. Registry Migration and Contract

- [x] 1.1 Add an Alembic revision after `20260622_0006` that seeds `WTI`, `SPY`, and `QQQ` with the specified asset classes and `TWELVE_DATA` mappings.
- [x] 1.2 Implement idempotent canonical-symbol upserts and guarded downgrade deletion for all three mappings.
- [x] 1.3 Extend integration tests for exact seeded rows, idempotency, preservation of existing mappings, downgrade safety, and canonical ordering.
- [x] 1.4 Extend symbol API tests and schema documentation so `ETF` is an accepted public asset-class value.

## 2. Generalize the Twelve Data Provider Boundary

- [x] 2.1 Rename Forex-specific Twelve Data REST provider types, factories, constants, and dependency names to asset-neutral equivalents.
- [x] 2.2 Rename Forex-specific Twelve Data WebSocket provider types, candle builder names, application state fields, and tests to asset-neutral equivalents.
- [x] 2.3 Preserve temporary compatibility aliases only where they reduce refactor risk, and remove unused Forex-only names before completion.
- [x] 2.4 Replace the Forex-named symbol allowlist with an explicit supported Twelve Data instrument allowlist containing existing symbols plus `WTI`, `SPY`, and `QQQ`.
- [x] 2.5 Keep all Twelve Data SDK imports, raw payloads, callback/thread behavior, and exceptions inside `app/providers/`.
- [x] 2.6 Add regression tests proving existing Forex, XAU/USD, and US stock behavior remains unchanged after generalization.

## 3. REST Quote and Candle Normalization

- [x] 3.1 Add provider tests that WTI, SPY, and QQQ latest-price requests use their matching provider symbols and preserve decimal precision.
- [x] 3.2 Add provider tests that WTI, SPY, and QQQ OHLC time series normalize into repository-owned candles for every supported timeframe.
- [x] 3.3 Preserve valid SPY and QQQ provider volume exactly.
- [x] 3.4 Normalize omitted or null WTI volume to exact decimal zero while rejecting malformed, negative, or non-finite supplied volume.
- [x] 3.5 Add quote service and route tests for WTI/ETF requests, mixed Binance/Twelve Data requests, cache behavior, and isolated provider failures.
- [x] 3.6 Add candle service and route tests for WTI/ETF provider fills, persisted-only reads, cache use, and provider error mapping.

## 4. ETF Market Session Policy

- [x] 4.1 Add an ETF session policy using Monday-Friday 09:30 inclusive through 16:00 exclusive in `America/New_York`.
- [x] 4.2 Add ETF daily eligibility using Monday-Friday UTC date labels.
- [x] 4.3 Select the ETF policy from persisted asset class `ETF`.
- [x] 4.4 Add DST-aware tests for pre-open, open, close, post-close, weekends, and daily labels.
- [x] 4.5 Verify historical expected-slot calculation excludes ETF closed-session ranges.
- [x] 4.6 Verify provider, repository, current-cache, stream-cache, and persistence boundaries reject closed-session ETF candles.

## 5. WTI Market Session Policy

- [x] 5.1 Add a WTI commodity session policy for Sunday 18:00 inclusive through Friday 17:00 exclusive in `America/New_York`.
- [x] 5.2 Exclude the Monday-through-Thursday 17:00 inclusive to 18:00 exclusive maintenance window.
- [x] 5.3 Add WTI daily eligibility using Monday-Friday UTC date labels.
- [x] 5.4 Select the WTI policy without applying it to unrelated `COMMODITY` symbols such as XAU/USD.
- [x] 5.5 Add DST-aware tests for weekly close, weekly reopen, daily maintenance, open periods, and daily labels.
- [x] 5.6 Verify historical expected-slot calculation and all candle boundaries exclude closed WTI slots without synthesizing provider gaps.

## 6. Twelve Data WebSocket Support

- [x] 6.1 Allow WTI, SPY, and QQQ quote and candle subscriptions on the shared process-local Twelve Data WebSocket connection.
- [x] 6.2 Add normalization tests for valid WTI/ETF price events, canonical mapping, malformed events, and unknown symbols.
- [x] 6.3 Reuse the derived candle builder for WTI and ETF price ticks while applying each symbol's selected session policy.
- [x] 6.4 Emit `MARKET_CLOSED` for closed WTI and ETF candle interests while keeping quote interests independent.
- [x] 6.5 Transition reopened WTI and ETF candle interests through `CONNECTING` to `SUBSCRIBED`.
- [x] 6.6 Add tests for mixed Forex/WTI/ETF subscriptions, connection reuse, reference-counted unsubscribe, and shutdown cleanup.
- [x] 6.7 Add stream manager tests proving closed-session WTI/ETF candles are not fanned out, cached, or persisted.

## 7. Documentation and OpenSpec Synchronization

- [x] 7.1 Update `docs/api-contract.md` with WTI, SPY, QQQ, the `ETF` asset class, and session semantics.
- [x] 7.2 Update `docs/spec.md`, `docs/system-design.md`, and `docs/tech-stack.md` to describe the generalized Twelve Data adapter and new coverage.
- [x] 7.3 Reconcile `docs/assets.md` current coverage with the actual seeded/runtime-supported registry.
- [x] 7.4 Update README examples for WTI and ETF quote, candle, and WebSocket requests.
- [x] 7.5 Sync the completed delta requirements into the main OpenSpec specifications when implementation is ready for completion.

## 8. Verification

- [x] 8.1 Run `openspec validate add-twelvedata-wti-etfs --strict`.
- [x] 8.2 Run focused migration, provider, session, quote, candle, and stream tests.
- [x] 8.3 Run the complete unit test suite.
- [x] 8.4 Run relevant PostgreSQL integration tests when `TEST_DATABASE_URL` is available.
- [x] 8.5 Run `ruff check .`, `ruff format --check .`, and `mypy app`.
- [x] 8.6 Run `git diff --check` and verify no provider secrets or live API payloads were committed.
- [ ] 8.7 Perform live smoke checks for `WTI`, `SPY`, and `QQQ` REST quotes, representative candle ranges, and WebSocket price subscriptions with the configured Twelve Data account.
