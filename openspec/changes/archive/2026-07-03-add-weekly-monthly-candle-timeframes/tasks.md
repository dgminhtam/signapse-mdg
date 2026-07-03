## 1. Timeframe Model

- [x] 1.1 Set the supported timeframe registry to `1m`, `5m`, `15m`, `30m`, `1h`, `1d`, `1w`, and `1mo`.
- [x] 1.2 Add the smallest calendar-period helper needed to get the next open for `1mo`.
- [x] 1.3 Update request range validation so `1mo` expected counts do not use a fake fixed 30-day duration.

## 2. Scheduling And Providers

- [x] 2.1 Extend candle schedule gap detection to handle `30m`, `1w`, and consecutive calendar-month opens.
- [x] 2.2 Map all eight public timeframes in Twelve Data candle requests.
- [x] 2.3 Map all eight public timeframes in Binance and yfinance candle requests.
- [x] 2.4 Derive weekly/monthly close times from the actual provider open time and requested period.

## 3. Tests And Docs

- [x] 3.1 Add focused unit coverage for accepting all eight timeframes, rejecting unknown values, and counting monthly ranges by calendar opens.
- [x] 3.2 Add provider mapping/normalization coverage for `30m`, weekly, and monthly candles.
- [x] 3.3 Update public docs to list `1m`, `5m`, `15m`, `30m`, `1h`, `1d`, `1w`, and `1mo` as supported historical candle timeframes.
- [x] 3.4 Run `uv run pytest` and `uv run ruff check .`.
