## 1. Request Contract and Clock Semantics

- [x] 1.1 Add an injectable UTC request clock to candle request parsing.
- [x] 1.2 Resolve an omitted `to` to one captured request-time UTC instant.
- [x] 1.3 Keep an explicitly empty or whitespace-only `to` invalid.
- [x] 1.4 Remove timeframe-alignment rejection for valid explicit `from` and `to` instants.
- [x] 1.5 Preserve required UTC validation, `from < to`, and exact resolved response boundaries.
- [x] 1.6 Add parser and route tests for omitted `to`, explicit `to`, empty `to`, unaligned boundaries, and deterministic response serialization.

## 2. Request Size Protection

- [x] 2.1 Replace integer slot-count pre-validation with ceiling-based elapsed-duration counting.
- [x] 2.2 Preserve `MAX_CANDLE_RANGE_DAYS` enforcement for explicit and defaulted `to`.
- [x] 2.3 Add boundary tests proving partial slots cannot bypass `MAX_CANDLES_PER_REQUEST`.
- [x] 2.4 Add service-level exact eligible-count enforcement after symbol and schedule resolution.
- [x] 2.5 Ensure oversized requests fail before provider access with `INVALID_TIME_RANGE`.

## 3. Candle Schedule Abstraction

- [x] 3.1 Define a repository-owned candle schedule protocol for enumerating expected open times and provider fetch sections.
- [x] 3.2 Implement the existing epoch-aligned duration schedule for Binance and compatible series.
- [x] 3.3 Add schedule selection from persisted provider, provider symbol, asset class, and timeframe.
- [x] 3.4 Capture real Twelve Data candle timestamps for WTI, SPY, and QQQ at `1m`, `5m`, `15m`, `1h`, and `1d`.
- [x] 3.5 Configure verified Twelve Data schedule anchors without assuming hourly `:30` applies to every interval.
- [x] 3.6 Combine schedule enumeration with existing market-session eligibility policies.
- [x] 3.7 Add unit tests for UTC/DST boundaries, partial public ranges, closed sessions, and daily labels.

## 4. Gap Detection and Provider Fetch Windows

- [x] 4.1 Replace duration stepping from public `from` with expected opens from the selected candle schedule.
- [x] 4.2 Match persisted complete candles to expected slots by their actual open timestamps.
- [x] 4.3 Group missing expected opens into minimal provider fetch sections.
- [x] 4.4 Expand provider fetch windows where required to include offset edge candles while preserving the exact public filter.
- [x] 4.5 Calculate provider limits from expected schedule slots plus documented boundary allowance.
- [x] 4.6 Add tests proving a persisted `:30` candle prevents repeated fills for a corresponding Twelve Data schedule slot.
- [x] 4.7 Add regression tests for Binance epoch-aligned gaps, overlapping provider rows, caches, and natural missing candles.

## 5. Provider Timestamp Preservation

- [x] 5.1 Preserve valid Twelve Data open timestamps exactly during normalization.
- [x] 5.2 Derive close time from the actual provider open time and interval duration.
- [x] 5.3 Filter normalized provider rows using exact `[from, to)` public boundaries.
- [x] 5.4 Add fixtures for valid offset hourly candles and unaligned edge ranges.
- [x] 5.5 Verify persistence identity and response ordering continue to use actual open time.

## 6. Twelve Data Empty-Range Classification

- [x] 6.1 Add an internal typed representation for a recognized Twelve Data no-data time-series result.
- [x] 6.2 Narrowly classify the structured “no data available on the specified dates” response as an empty result.
- [x] 6.3 Keep authentication, entitlement, rate-limit, invalid interval, unknown symbol, timeout, transport, and unknown errors mapped to `ProviderUnavailableError`.
- [x] 6.4 Add HTTP-client and provider tests for empty ranges and every retained failure category.
- [x] 6.5 Add route/service tests confirming a valid no-data range returns HTTP 200 with `candles: []`.

## 7. Documentation and OpenSpec Synchronization

- [x] 7.1 Update `docs/api-contract.md` so `to` is optional and public boundaries need not be timeframe-aligned.
- [x] 7.2 Update `docs/spec.md` and `docs/system-design.md` with request-time resolution and provider-aware schedules.
- [x] 7.3 Update README examples to include a candle request without `to`.
- [x] 7.4 Document that response `to` is always present and contains the resolved request boundary.
- [x] 7.5 Document that provider open times remain authoritative and empty provider ranges are successful.
- [x] 7.6 Sync the completed delta requirements into the main historical-candles spec.

## 8. Verification

- [x] 8.1 Run `openspec validate relax-candle-range-and-default-to-now --strict`.
- [x] 8.2 Run focused parser, schedule, gap, Twelve Data provider, candle service, and route tests.
- [x] 8.3 Run the complete unit test suite.
- [x] 8.4 Run PostgreSQL candle integration tests when `TEST_DATABASE_URL` is available.
- [x] 8.5 Run live WTI, SPY, and QQQ smoke tests for explicit ranges and omitted `to` with the configured Twelve Data account.
- [x] 8.6 Run `ruff check .`, `ruff format --check .`, `mypy app`, and `git diff --check`.
