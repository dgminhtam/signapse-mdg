## 1. Symbol Calendar Config Plumbing

- [x] 1.1 Add nullable calendar config fields to the internal `SupportedSymbol` domain model.
- [x] 1.2 Map `calendar_source`, `calendar_name`, and `calendar_timezone` from symbol repository rows.
- [x] 1.3 Update unit test fixtures that construct `SupportedSymbol` values.

## 2. Market Session Policy

- [x] 2.1 Add a pandas-market-calendars-backed `MarketSessionPolicy` using cached local schedules.
- [x] 2.2 Route `get_market_session_policy()` through inline calendar config when present.
- [x] 2.3 Preserve internal always-open behavior for `internal:24/7`.
- [x] 2.4 Preserve existing Forex/XAU weekly-session behavior instead of using pandas `FOREX` directly.
- [x] 2.5 Fall back to existing asset-class policies when config is absent or unsupported.

## 3. Historical Candle Coverage

- [x] 3.1 Cover pandas calendar intraday closed sessions and break windows.
- [x] 3.2 Cover pandas calendar daily closed labels.
- [x] 3.3 Cover historical service gap splitting and filtering through the existing policy boundary.

## 4. Stream Coverage

- [x] 4.1 Cover derived stream candles outside pandas sessions and break windows.
- [x] 4.2 Cover stream `MARKET_CLOSED` and reopen transitions through inline calendar config.
- [x] 4.3 Cover Forex stream behavior remains weekly-session based.

## 5. Verification

- [x] 5.1 Run `openspec.cmd validate use-inline-calendar-config-for-candle-filtering --strict`.
- [x] 5.2 Run `uv run pytest`.
- [x] 5.3 Run `uv run ruff check .`.
- [x] 5.4 Run `uv run mypy app`.
