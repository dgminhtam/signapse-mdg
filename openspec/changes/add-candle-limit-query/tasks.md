## 1. Request Shape

- [x] 1.1 Extend the internal candle request model to represent range mode and limit mode.
- [x] 1.2 Parse optional `limit` in `GET /v1/candles`.
- [x] 1.3 Reject ambiguous `from` plus `limit` requests.
- [x] 1.4 Enforce `limit` is an integer from 1 through `MAX_CANDLES_PER_REQUEST`.

## 2. Schedule And Service

- [x] 2.1 Add a schedule helper that derives the latest N eligible opens before a resolved `to`.
- [x] 2.2 Reuse existing market-session policy filtering while deriving count-mode opens.
- [x] 2.3 Route count mode through the existing persistence, cache, provider gap-fill, and merge flow.
- [x] 2.4 Preserve provider `limit` as a bounded fetch safety cap, not the source of count semantics.

## 3. Coverage

- [x] 3.1 Cover valid count requests with omitted `to`.
- [x] 3.2 Cover count requests crossing closed sessions, holidays, or break windows.
- [x] 3.3 Cover provider natural gaps returning fewer than `limit` candles.
- [x] 3.4 Cover cached forming candle merge in count mode.
- [x] 3.5 Cover invalid `limit`, `from` plus `limit`, and response shape.

## 4. Verification

- [x] 4.1 Run `openspec.cmd validate add-candle-limit-query --strict`.
- [x] 4.2 Run `uv run pytest`.
- [x] 4.3 Run `uv run ruff check .`.
- [x] 4.4 Run `uv run mypy app`.
