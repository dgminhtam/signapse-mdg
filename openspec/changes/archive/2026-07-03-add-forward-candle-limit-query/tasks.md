## 1. Request Parsing

- [x] 1.1 Update candle request parsing to allow `from+limit` without `to`.
- [x] 1.2 Preserve backward count for `to+limit` and `limit`-only requests.
- [x] 1.3 Preserve explicit range mode for `from+to` without `limit`.
- [x] 1.4 Reject `from+to+limit` with `INVALID_TIME_RANGE`.

## 2. Count Derivation

- [x] 2.1 Add a schedule helper that derives the next N eligible opens at or after `from`.
- [x] 2.2 Support fixed-duration and calendar-month forward walking.
- [x] 2.3 Use the derived forward opens to resolve the provider/cache/persistence range.
- [x] 2.4 Keep provider `limit` as `gap.expected_count + 1`.

## 3. Tests

- [x] 3.1 Cover `from+limit` forward count with unaligned `from`.
- [x] 3.2 Cover forward count crossing closed sessions.
- [x] 3.3 Cover `from+to+limit` rejection.
- [x] 3.4 Cover existing `from+to`, `to+limit`, and `limit`-only behavior remains unchanged.

## 4. Validation

- [x] 4.1 Run `openspec.cmd validate add-forward-candle-limit-query --strict`.
- [x] 4.2 Run the focused candle tests.
