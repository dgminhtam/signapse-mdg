## Why

Keeping both `TWELVEDATA_API_KEY` and `TWELVEDATA_API_KEYS` makes deployment confusing and caused a
real misconfiguration where only the old single-key value was loaded. The gateway should expose one
Twelve Data credential setting: comma-separated `TWELVEDATA_API_KEYS`.

## What Changes

- **BREAKING**: Remove support for `TWELVEDATA_API_KEY`.
- Keep `TWELVEDATA_API_KEYS` as the only Twelve Data API key setting.
- Remove single-key merge/backward-compatibility logic from typed settings and tests.
- Update runtime wiring, examples, deploy docs, and active OpenSpec specs/docs to stop referencing
  the old setting.
- Keep rotation behavior unchanged: ordered, de-duplicated keys from `TWELVEDATA_API_KEYS`.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `provider-sdk-integration`: Twelve Data settings no longer accept the old single-key setting.

## Impact

- Affected code: `app/core/config.py`, Twelve Data route/backfill/stream wiring only if needed,
  settings tests, provider tests that construct `Settings`.
- Public APIs: none.
- Deployment: environment configs must use `TWELVEDATA_API_KEYS`; existing deployments using only
  `TWELVEDATA_API_KEY` must rename the variable.
- Database/migrations: none.
