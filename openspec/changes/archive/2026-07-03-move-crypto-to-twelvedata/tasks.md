## 1. Registry Data

- [x] 1.1 Add an Alembic data migration that updates `BTC/USD` to `TWELVE_DATA:BTC/USD` and
  `ETH/USD` to `TWELVE_DATA:ETH/USD`.
- [x] 1.2 Add a downgrade path or documented rollback SQL that restores `BINANCE_SPOT:BTCUSD` and
  `BINANCE_SPOT:ETHUSD`.
- [x] 1.3 Update supported-symbol registry tests for the new crypto provider mappings.

## 2. Twelve Data Provider Support

- [x] 2.1 Add `BTC/USD` and `ETH/USD` to the Twelve Data supported provider-symbol allowlist.
- [x] 2.2 Update Twelve Data REST provider tests proving quote and candle calls accept both crypto
  provider symbols.
- [x] 2.3 Update Twelve Data stream provider tests proving subscriptions accept both crypto provider
  symbols.

## 3. Route Behavior

- [x] 3.1 Update quote routing tests so `BTC/USD` and `ETH/USD` refresh through the Twelve Data
  provider mapping.
- [x] 3.2 Update candle routing tests so `BTC/USD` and `ETH/USD` fetch missing ranges through
  Twelve Data.
- [x] 3.3 Update stream routing tests so `BTC/USD` and `ETH/USD` route through Twelve Data while
  Binance remains registered.

## 4. Documentation and Verification

- [x] 4.1 Update product/API/system docs that list `BTC/USD` and `ETH/USD` as Binance-backed.
- [x] 4.2 Document the existing-database SQL update needed for deployments that do not replay
  migrations from scratch.
- [x] 4.3 Run focused registry, quote, candle, stream, and Twelve Data provider tests.
- [x] 4.4 Run `uv run ruff check .` and `uv run mypy app`.
