## Context

Twelve Data accepts comma-separated `TWELVEDATA_API_KEYS` and builds SDK clients for REST quote and
candle calls, plus SDK WebSocket clients for streams. Binance does not need keys, and yfinance does
not use this credential model. The useful minimum is therefore Twelve Data-only key rotation, kept
behind the provider adapter boundary.

## Goals / Non-Goals

**Goals:**
- Allow deployments to configure one or more Twelve Data API keys.
- Preserve compatibility with the existing single-key setting.
- Rotate REST calls across healthy configured keys and cool down keys that hit quota/auth style
  provider failures.
- Keep provider errors sanitized and SDK details inside `app/providers/`.
- Keep WebSocket behavior stable by choosing a key only when connecting or reconnecting.

**Non-Goals:**
- No multi-provider fallback or per-asset provider priority.
- No database table or UI for managing keys.
- No distributed quota coordination across replicas.
- No changes to Binance or yfinance.
- No live WebSocket key swap while subscriptions are active.

## Decisions

### Add a Twelve Data-only key pool

Introduce a small process-local key pool for Twelve Data. It should hold a tuple of configured
keys, choose the next non-cooled key in round-robin order, and mark a key cooled down when the
adapter sees a provider failure that plausibly means quota/auth/key exhaustion.

Alternative considered: a generic provider credential manager. Rejected because only Twelve Data
needs this now.

### Use `TWELVEDATA_API_KEYS`

Use `TWELVEDATA_API_KEYS` as the comma-separated key input. The effective key list is de-duplicated
while preserving order.

Alternative considered: keep a separate singular variable. Rejected because one comma-separated
setting is enough and avoids operator confusion.

### Retry one alternate key for REST

For REST quote and candle operations, the adapter should attempt the operation with one selected
key. On a key-related provider failure, cool down that key and retry the same operation once with a
different healthy key. Other normalization failures and no-data responses should keep their current
behavior.

Alternative considered: retry every configured key. Rejected because it can multiply provider load
and hide real provider outages.

### Choose WebSocket key at connection time

The stream provider should pick one healthy key when creating a Twelve Data WebSocket client. It
should not rotate a live connected socket because reconnecting and resubscribing is already the
natural boundary for changing stream credentials.

Alternative considered: rotate keys on heartbeat or stream errors. Rejected as too much state for
the current need.

## Risks / Trade-offs

- Multiple replicas do not share key cooldown state -> acceptable for now; add shared state only if
  deployments need it.
- Some provider errors may not distinguish quota/auth from other failures -> use conservative
  cooldown and keep errors sanitized.
- Retrying one alternate key can still spend an extra credit -> bounded retry keeps the blast small.
- WebSocket may keep using a weak key until reconnect -> acceptable because live key swaps add
  subscription complexity.
