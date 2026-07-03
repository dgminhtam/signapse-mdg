## 1. Settings

- [x] 1.1 Remove `twelvedata_api_key` from typed settings.
- [x] 1.2 Simplify `twelvedata_effective_api_keys()` to parse only `TWELVEDATA_API_KEYS`.
- [x] 1.3 Ensure empty values are skipped and duplicate keys are de-duplicated in order.

## 2. Runtime Wiring

- [x] 2.1 Verify quote, candle, stream, and backfill wiring pass only the effective plural key list.
- [x] 2.2 Ensure missing `TWELVEDATA_API_KEYS` leaves Twelve Data unconfigured without breaking app startup.

## 3. Documentation and Specs

- [x] 3.1 Remove `TWELVEDATA_API_KEY` from `.env.example`, README, deploy docs, system design, tech stack, and product spec.
- [x] 3.2 Update active OpenSpec specs/change docs that describe current Twelve Data configuration.
- [x] 3.3 Keep archived OpenSpec history unchanged unless a live validation target requires otherwise.

## 4. Tests and Validation

- [x] 4.1 Update settings tests for one-key and multi-key `TWELVEDATA_API_KEYS` parsing.
- [x] 4.2 Update route/backfill tests that still pass `Settings(twelvedata_api_key=...)`.
- [x] 4.3 Add or update a regression check that the singular setting is not part of `Settings`.
- [x] 4.4 Run focused settings/Twelve Data wiring tests, `uv run ruff check .`, and `uv run mypy app`.
