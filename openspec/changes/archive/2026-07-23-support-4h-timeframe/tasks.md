## 1. Shared Timeframe Contract

- [x] 1.1 Add canonical `4h` with a 240-minute duration to the shared timeframe registry and allow
  it in WebSocket request validation while keeping `h4` unsupported.
- [x] 1.2 Extend request, duration, alignment, close-time, range-limit, and backfill tests for `4h`.

## 2. Provider Integration

- [x] 2.1 Add direct `4h` interval mappings to the Twelve Data, yfinance, and retained Binance Spot
  REST candle adapters.
- [x] 2.2 Add the Binance Spot WebSocket `4h` kline mapping; reuse the existing tick-derived candle
  builder unchanged for Twelve Data and yfinance streams.
- [x] 2.3 Extend provider tests to verify interval forwarding, normalized four-hour close times,
  stream bucket rollover, and sanitized rejection of unknown intervals.

## 3. Asset and Session Coverage

- [x] 3.1 Add parameterized coverage showing `4h` requests route for representative enabled crypto,
  Forex, commodity, US stock, ETF, and stock-index symbols.
- [x] 3.2 Verify four-hour UTC bucket alignment and existing market-session eligibility at Forex
  weekly boundaries and configured exchange sessions.

## 4. Documentation and Verification

- [x] 4.1 Update `docs/spec.md` historical and WebSocket timeframe lists and behavior to include
  canonical `4h`.
- [x] 4.2 Run the relevant unit and integration tests, then `uv run ruff check .` and
  `uv run mypy app`.
