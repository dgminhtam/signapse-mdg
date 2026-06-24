## 1. Shared Provider Normalization

- [x] 1.1 Add `app/providers/normalization.py` with shared Decimal parsing that preserves current provider edge cases.
- [x] 1.2 Replace matching Decimal parser copies in Binance, Twelve Data REST, Twelve Data stream, yfinance REST, and yfinance stream providers.
- [x] 1.3 Replace REST candle provider duration maps with `get_timeframe(provider_interval).duration` and preserve `ProviderUnavailableError` for unknown intervals.

## 2. Provider Setup Cleanup

- [x] 2.1 Extract shared Binance REST SDK client construction and keep existing quote/candle builder entry points.
- [x] 2.2 Collapse duplicate yfinance quote/candle builders while preserving existing imports or wrappers needed by route tests.
- [x] 2.3 Remove the Twelve Data stream candle-builder alias and simplify duplicated symbol lookup logic.
- [x] 2.4 Simplify WebSocket route registry mapping after `list_enabled()` without changing unsupported-symbol behavior.

## 3. Verification

- [x] 3.1 Run provider unit tests covering Binance, Twelve Data, and yfinance normalization and builders.
- [x] 3.2 Run quote, candle, and stream route tests to confirm public payloads and dependency overrides are unchanged.
- [x] 3.3 Run `uv run ruff check .` and `uv run mypy app`.
