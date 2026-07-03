## Context

The previous rotation change kept `TWELVEDATA_API_KEY` for backward compatibility and added
`TWELVEDATA_API_KEYS` for comma-separated rotation. That compatibility now creates more confusion
than value because operators may set one key in the old variable and expect two-key rotation.

## Goals / Non-Goals

**Goals:**
- Make `TWELVEDATA_API_KEYS` the single source of truth for Twelve Data REST and stream credentials.
- Remove `twelvedata_api_key` from typed settings and any effective-key merge logic.
- Update docs and tests so new deployments have one obvious variable to set.
- Preserve existing key rotation, cooldown, retry, and WebSocket connect-time selection behavior.

**Non-Goals:**
- No provider fallback.
- No distributed quota or shared cooldown state.
- No key validation endpoint or startup provider health check.
- No database changes.

## Decisions

### Use only `TWELVEDATA_API_KEYS`

`TWELVEDATA_API_KEYS` already supports both one key and many keys because a single value is valid
comma-separated input. Removing the singular variable leaves one deploy path.

Alternative considered: keep both and improve docs. Rejected because the current failure mode is
operator confusion, not missing documentation.

### Keep parsing simple

The settings helper should split `TWELVEDATA_API_KEYS` on commas, trim whitespace, remove empty
values, and de-duplicate while preserving order. No JSON array, no secret manager abstraction.

Alternative considered: add a new typed list setting. Rejected because environment values are
already string-based and comma-separated is enough.

### Do not rewrite archived OpenSpec history

Implementation should update active specs/docs/change artifacts that describe current behavior.
Archived OpenSpec changes can keep historical mentions of `TWELVEDATA_API_KEY`.

Alternative considered: remove every archived mention. Rejected because it rewrites history without
changing runtime behavior.

## Risks / Trade-offs

- Existing deployments using only `TWELVEDATA_API_KEY` will lose live Twelve Data fills until they
  rename the variable -> Document the breaking rename clearly.
- Local `.env` files may still contain the old name -> examples and deploy docs should show only
  `TWELVEDATA_API_KEYS`.
- Tests may still pass because Pydantic ignores extra env/settings fields -> add explicit tests for
  key parsing and no singular setting.
