## 1. Approved yfinance Catalog

- [x] 1.1 Expand `SUPPORTED_YFINANCE_PROVIDER_SYMBOLS` to the exact 23 yfinance symbols in the
  approved mapping matrix, excluding `GC=F` and `XAUUSD=X`.
- [x] 1.2 Update quote, historical-candle, and stream adapter tests to prove the shared allowlist
  accepts every approved symbol and rejects unapproved symbols before upstream I/O.

## 2. Provider Mapping Seed Migration

- [x] 2.1 Add Alembic revision `0019` after `20260727_0018` with immutable previous/target mapping
  constants and transactional reconciliation of the 24 active defaults plus five inactive
  alternatives.
- [x] 2.2 Preserve unknown custom mapping rows, remove only explicit obsolete historical seed
  pairs, mirror each active default into the legacy provider columns, and validate the completed
  seed in the migration.
- [x] 2.3 Implement downgrade to restore the known `0018` mappings and legacy values, remove only
  rows introduced by `0019`, and preserve unknown mappings and candle rows.

## 3. Database and Runtime Verification

- [x] 3.1 Add PostgreSQL integration coverage for a fresh upgrade containing 24 canonical assets,
  29 approved mappings, exactly 24 active defaults, five inactive alternatives, and no XAU
  yfinance proxy.
- [x] 3.2 Add migration tests for repeatable reconciliation, disabled assets, custom mapping
  preservation, provider-identity collision failure, and legacy-column equality with active
  defaults.
- [x] 3.3 Add incremental upgrade/downgrade coverage proving supported-symbol rows, unknown
  mappings, audit timestamps where preserved, and provider-owned candle rows are not lost or
  relabeled.
- [x] 3.4 Run route-level regression tests proving the migrated legacy values route quote, candle,
  and stream operations through the same approved default without fallback.
- [x] 3.5 Run a time-bounded live yfinance smoke check for approved quote/history symbols and record
  WebSocket tick or no-tick observations without adding polling, remapping, or fallback.

## 4. Documentation

- [x] 4.1 Update registry and system-design documentation with the final 24-asset/29-mapping
  matrix, the five manual alternatives, the XAU Twelve Data-only decision, and the temporary
  active/legacy synchronization invariant.
- [x] 4.2 Document the yfinance rollout ordering and the fact that changing providers starts a new
  provider-owned candle history rather than relabeling existing candles.

## 5. Quality Checks

- [x] 5.1 Run the focused PostgreSQL migration and provider-adapter test suites with
  `TEST_DATABASE_URL` pointing to the disposable test database.
- [x] 5.2 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and
  `uv run mypy app`.
- [x] 5.3 Run strict OpenSpec validation for `seed-24-asset-provider-mappings`.
