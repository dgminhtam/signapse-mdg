## 1. Dependency and Boundary

- [x] 1.1 Add a pinned `yfinance` dependency using `uv` and update the lockfile.
- [x] 1.2 Verify the package can be imported from provider-owned code without requiring API keys or startup configuration.
- [x] 1.3 Add or extend import-boundary tests proving yfinance imports do not appear outside `app/providers/`.
- [x] 1.4 Confirm application startup creates no yfinance client, session, WebSocket, or background task.

## 2. Registry Model and Migration

- [x] 2.1 Add `STOCK_INDEX` wherever public supported-symbol asset classes are validated or serialized.
- [x] 2.2 Add an Alembic revision after the current symbol seed revisions for the ten `YFINANCE` mappings.
- [x] 2.3 Implement idempotent canonical-symbol upserts for `XAG/USD`, `BRENT`, `SPX`, `NDX`, `DJI`, `NATGAS`, `COFFEE`, `SUGAR`, `WHEAT`, and `CORN`.
- [x] 2.4 Implement guarded downgrade deletion that removes only rows still matching the seeded `YFINANCE` mappings.
- [x] 2.5 Preserve all existing `BINANCE_SPOT` and `TWELVE_DATA` registry rows unchanged.

## 3. Tests

- [x] 3.1 Add migration tests for exact seeded rows, idempotency, canonical ordering, and guarded downgrade behavior.
- [x] 3.2 Add supported-symbol API tests showing `STOCK_INDEX` rows use the existing response shape.
- [x] 3.3 Add regression tests proving quote, candle, and WebSocket paths do not call yfinance in this change.
- [x] 3.4 Run the focused migration and symbol API test suite.

## 4. Documentation and Specs

- [x] 4.1 Update `docs/assets.md` to move the ten seeded assets from planned providerless coverage to provider-mapped coverage as appropriate.
- [x] 4.2 Update `docs/api-contract.md` with `STOCK_INDEX` and the new `/v1/symbols` registry entries.
- [x] 4.3 Update `docs/system-design.md` and `docs/tech-stack.md` with the yfinance dependency, `YFINANCE` registry mappings, and no-routing scope.
- [x] 4.4 Document that yfinance commodity mappings are futures or rolling-futures proxies, especially `XAG/USD -> SI=F`.

## 5. Verification

- [x] 5.1 Run `openspec validate add-yfinance-symbol-seed --strict`.
- [x] 5.2 Run `uv run pytest` or the narrowest reliable equivalent plus affected integration tests when `TEST_DATABASE_URL` is available.
- [x] 5.3 Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy app`.
- [x] 5.4 Run `git diff --check` and verify no provider credentials or live Yahoo/yfinance payloads were committed.
