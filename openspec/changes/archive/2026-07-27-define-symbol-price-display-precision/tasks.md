## 1. Registry Schema and Mapping

- [x] 1.1 Add an Alembic migration that creates nullable `price_display_decimals`, backfills the
  agreed values for all 24 current symbols, verifies no enabled row remains null, makes the column
  non-null without a default, adds the inclusive 0-to-18 check constraint, and provides a safe
  downgrade.
- [x] 1.2 Add required `price_display_decimals` fields to `SupportedSymbolModel` and
  `SupportedSymbol`, then map the persisted value in `PostgresSymbolRepository`.

## 2. Public Symbol Metadata

- [x] 2.1 Add `price_display_decimals` to `SymbolResponse` so `GET /v1/symbols` returns
  `priceDisplayDecimals` from the persisted registry value.
- [x] 2.2 Update `docs/spec.md`, `docs/assets.md`, and `docs/system-design.md` to document the
  per-symbol values, presentation-only semantics, consumer metadata flow, and raw-price fallback.

## 3. Verification

- [x] 3.1 Add migration integration coverage for all 24 backfilled values, the non-null
  requirement, the 0-to-18 constraint, and the absence of a default.
- [x] 3.2 Update symbol domain/repository/API tests to require and serialize
  `priceDisplayDecimals`, including `XAU/USD` value `2`.
- [x] 3.3 Add focused regression coverage proving display metadata does not quantize latest quote,
  historical price, historical candle, or WebSocket quote/candle decimal strings and does not
  appear in those exact response/event shapes.
- [x] 3.4 Run `uv run pytest`, `uv run ruff check .`, and `uv run mypy app`.
