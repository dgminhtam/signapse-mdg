## Context

Revision `20260727_0018` provides the final normalized schema: each supported asset can own multiple
provider mappings, with at most one mapping selected by `is_active`. It intentionally leaves
runtime routing on the temporary legacy provider columns. The current catalog has 24 assets but
only the one-to-one mappings copied from those legacy columns, and the yfinance adapters accept
only the ten originally introduced yfinance symbols.

This change establishes the approved catalog configuration without attempting the later repository
cutover. The target is 29 owned seed mappings: 24 active defaults and five inactive yfinance
alternatives. `XAU/USD` remains Twelve Data-only because Yahoo has no approved equivalent spot
mapping; `GC=F` is a futures proxy and is excluded.

## Goals / Non-Goals

**Goals:**

- Reconcile the current 24 assets to the approved provider-symbol matrix.
- Guarantee exactly one approved active default per canonical asset.
- Keep legacy provider columns equal to the active default while current releases still read them.
- Preserve unrelated custom mapping rows while removing only obsolete mappings owned by historical
  seeds.
- Make every approved yfinance symbol acceptable to quote, candle, and stream adapters.
- Provide deterministic upgrade, repeat execution, validation, and downgrade behavior.

**Non-Goals:**

- No automatic fallback or provider priority.
- No different provider for quote, candle, and stream.
- No API or administrative workflow for switching providers.
- No repository cutover from legacy columns to an active-mapping join.
- No removal of legacy columns and no rewrite or deletion of provider-owned candle history.
- No `GC=F`, `XAUUSD=X`, or other proxy mapping for `XAU/USD`.

## Decisions

### Add one immutable seed migration after `20260727_0018`

Revision `0019` will contain explicit previous and target mapping constants. Alembic will not
import application configuration, keeping the historical migration reproducible after application
code changes.

Alternative considered: seed at application startup. Rejected because startup writes are
non-deterministic across replicas and do not provide a transactional schema/data revision.

### Reconcile known seeds without deleting unknown mappings

The upgrade will:

1. resolve all 24 canonical `supported_symbols` rows and fail if any are missing;
2. set existing active mappings for those assets inactive to satisfy the partial unique index;
3. upsert all 29 approved target mappings;
4. delete only explicit obsolete provider pairs created by known earlier seed revisions;
5. mark the 24 approved defaults active;
6. copy each default provider and provider symbol into the corresponding legacy columns; and
7. validate the target rows, active count, unique selection, legacy mirror, and absence of seeded
   `GC=F`.

An unknown custom mapping remains present but inactive when the approved default is selected.
Provider/provider-symbol collisions owned by another canonical asset fail the migration instead of
silently moving or deleting data.

Alternative considered: delete every mapping not present in the matrix. Rejected because the
database may contain manually configured mappings not owned by this seed.

### Keep the active mapping and legacy columns synchronized during compatibility

The migration updates both representations in one transaction. Until runtime routing joins
`symbol_provider_mappings`, any later manual provider switch must atomically change `is_active` and
the two legacy columns. This change does not add a switching service because none is currently
required.

Alternative considered: update only `is_active`. Rejected because all three deployed market-data
paths still read the legacy columns and would ignore the new default.

### Use one shared yfinance allowlist

`SUPPORTED_YFINANCE_PROVIDER_SYMBOLS` remains the single repository-owned allowlist used by quote,
candle, and stream adapters and expands from ten to the 23 yfinance symbols present in the approved
matrix. No per-route allowlist or symbol translation table is introduced.

Alternative considered: allow every Yahoo ticker. Rejected because the registry is a controlled
catalog and unsupported identifiers must fail before an upstream request.

### Preserve provider-owned candle identity

Existing candle rows remain keyed by their recorded provider and provider symbol. Changing an
asset's active default does not relabel old data; future requests and persistence use the new
active provider identity. This avoids mixing spot, futures, exchange, or vendor histories.

## Risks / Trade-offs

- [Expanded yfinance symbols may be silent on WebSocket during some sessions] → preserve the
  existing `CONNECTING`/freshness behavior, add adapter contract coverage, and record a time-bounded
  live smoke check without adding polling or fallback.
- [Rolling deployment can expose new defaults to an old ten-symbol allowlist] → deploy the
  backward-compatible expanded allowlist before applying revision `0019`, or use a maintenance
  window with no mixed application versions.
- [Unknown custom mapping collides with an approved provider identity] → fail transactionally and
  require an operator to resolve the conflict; never steal the mapping.
- [Switching defaults makes prior provider candles unavailable to current-provider queries] →
  retain all rows under their original identity and accept a cold fill for the new provider.
- [Direct SQL can desynchronize active and legacy selections after migration] → document the
  compatibility invariant and test the migration mirror; a later runtime-cutover change removes
  this dual-write requirement.
- [Downgrade after operators modify seeded rows can be ambiguous] → downgrade touches only explicit
  revision-owned provider pairs and restores the known `0018` defaults; unknown rows are preserved.

## Migration Plan

1. Expand and test the shared yfinance allowlist in a backward-compatible application release.
2. Apply revision `0019` transactionally with provider-selection writes paused.
3. Validate 24 canonical assets, 24 active defaults, five approved inactive alternatives, legacy
   mirror equality, and no seeded XAU yfinance proxy.
4. Resume traffic and smoke-test quote, candle, and stream routing for each provider group.
5. On rollback, downgrade `0019`: restore the known `0018` active mappings and legacy values,
   remove only rows introduced by `0019`, and preserve unknown custom mappings and all candles.

## Open Questions

None. The provider matrix, absence of an XAU yfinance alternative, and no-fallback behavior are
explicitly approved.

## Implementation Verification

On 2026-07-27, a time-bounded live yfinance smoke check returned latest quotes and seven-day daily
history for all 23 approved yfinance symbols. During a 20-second WebSocket window, ticks arrived
for `AUDUSD=X`, `BTC-USD`, `ETH-USD`, `EURUSD=X`, `GBPUSD=X`, `JPY=X`, `NVDA`, `QQQ`, `SPY`, and
`TSLA`; the other 13 symbols produced no tick in that window. The no-tick result does not trigger
polling, remapping, or fallback.
