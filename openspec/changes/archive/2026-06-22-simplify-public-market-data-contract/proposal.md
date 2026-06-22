## Why

The latest-quotes response exposes provider-specific and unused fields that the current Java
consumer does not need. Reducing the public DTO now keeps provider mappings internal and avoids
creating compatibility obligations for fields that are null, redundant, or governed by internal
freshness policy.

## What Changes

- **BREAKING** Reduce each successful `GET /v1/quotes` item to exactly `symbol`, `price`, and
  `receivedAt`.
- Remove `assetClass`, `provider`, `providerSymbol`, `volume`, `providerTime`, and `stale` from the
  latest-quotes public response.
- Keep provider metadata, registry mappings, normalized domain data, cache TTL, stale thresholds,
  and per-symbol `DATA_STALE` behavior internal to the gateway.
- Keep the request format, decimal-string price serialization, response envelopes, ordering, and
  per-symbol error contract unchanged.
- Update API documentation and contract tests to describe and enforce the reduced response.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `latest-quotes`: Replace the successful quote representation with the minimal public DTO while
  preserving existing lookup, provider, cache, freshness, and error behavior.

## Impact

- Affects the `GET /v1/quotes` response model and serialization in `app/api/routes_quotes.py`.
- Requires updates to latest-quotes route and integration tests that assert provider metadata.
- Requires updates to `docs/spec.md`, `docs/system-design.md`, and relevant tech-stack guidance.
- Requires the Java consumer to stop deserializing the removed fields.
- Does not change the database schema, Binance SDK adapter, provider mappings, or
  `GET /v1/symbols`.
