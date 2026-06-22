## 1. Market Session Domain Policy

- [x] 1.1 Add a market-session policy protocol owned by the domain/service boundary.
- [x] 1.2 Implement an always-open policy for current non-Forex asset classes.
- [x] 1.3 Implement the Forex intraday weekly session using `America/New_York` and Sunday/Friday 17:00 boundaries.
- [x] 1.4 Implement the Forex `1d` Monday-through-Friday UTC label rule.
- [x] 1.5 Select the session policy from persisted `SupportedSymbol.asset_class` without changing registry schema.
- [x] 1.6 Add unit tests for exact close/reopen boundaries, summer EDT, winter EST, and DST transition weeks.
- [x] 1.7 Add the portable `tzdata` runtime dependency for consistent Windows/Linux behavior.

## 2. Session-Aware Historical Candle Service

- [x] 2.1 Filter persisted candles through the selected market-session policy before response merging.
- [x] 2.2 Update gap detection to consider only market-session eligible timeframe slots.
- [x] 2.3 Coalesce eligible missing slots into provider ranges split around the Forex weekend closure.
- [x] 2.4 Avoid provider calls when a Forex request contains only closed-session slots.
- [x] 2.5 Filter provider results before completion calculation and persistence.
- [x] 2.6 Filter the current candle cache before merging it into a historical response.
- [x] 2.7 Preserve current non-Forex gap detection, persistence, and cache behavior.

## 3. Twelve Data Defense-in-Depth

- [x] 3.1 Apply the Forex session policy to normalized Twelve Data intraday rows.
- [x] 3.2 Apply the Forex weekday-label rule to normalized Twelve Data daily rows.
- [x] 3.3 Ensure closed-session rows are discarded rather than treated as malformed provider payloads.
- [x] 3.4 Preserve open-session missing rows as natural gaps without synthesizing candles.
- [x] 3.5 Keep Twelve Data quote behavior unchanged.

## 4. Persisted Data Cleanup

- [x] 4.1 Add an Alembic data migration after the current Forex seed revision.
- [x] 4.2 Delete persisted intraday `FOREX` candles in the Friday 17:00 through Sunday 17:00 New York closed session.
- [x] 4.3 Delete persisted `1d` `FOREX` candles labeled Saturday or Sunday in UTC.
- [x] 4.4 Verify the cleanup leaves crypto and all non-Forex rows unchanged.
- [x] 4.5 Make downgrade a documented no-op because deleted provider candles cannot be reconstructed.

## 5. Tests

- [x] 5.1 Add service tests for requests spanning open Friday, closed weekend, and open Sunday ranges.
- [x] 5.2 Add service tests proving a closed-only Forex request returns an empty series without provider access.
- [x] 5.3 Add service tests proving persisted and cached weekend Forex candles are excluded.
- [x] 5.4 Add provider tests proving weekend rows are discarded while boundary and weekday rows remain.
- [x] 5.5 Add daily timeframe tests for weekday retention and weekend exclusion.
- [x] 5.6 Add migration integration tests for cleanup scope and no-op downgrade.
- [x] 5.7 Add regression tests proving crypto, quote HTTP, and WebSocket behavior remain unchanged.

## 6. Documentation

- [x] 6.1 Update `docs/spec.md` with the Signapse Forex weekly quote-session semantics.
- [x] 6.2 Update `docs/system-design.md` with session-aware gap calculation and provider filtering.
- [x] 6.3 Document the `America/New_York` DST-aware boundary and separate daily rule.
- [x] 6.4 Document that holidays, early closes, and exceptional closures remain out of scope.
- [x] 6.5 Update the runbook with a Friday-to-Monday verification example.

## 7. Verification

- [x] 7.1 Run `openspec validate filter-forex-weekend-candles --strict`.
- [x] 7.2 Run session policy, candle service, Twelve Data provider, route, and migration tests.
- [x] 7.3 Run relevant integration tests when `TEST_DATABASE_URL` is available.
- [x] 7.4 Run the complete unit test suite.
- [x] 7.5 Run `ruff check .`, `mypy app`, and `git diff --check`.
