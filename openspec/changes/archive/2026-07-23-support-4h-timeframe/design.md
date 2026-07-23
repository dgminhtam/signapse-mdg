## Context

The gateway has one shared fixed-duration timeframe registry, separate REST interval maps for
Binance Spot, Twelve Data, and yfinance, and a narrower WebSocket timeframe allowlist. Twelve Data
and yfinance stream candles are already built from price ticks using the shared duration model,
while Binance uses upstream kline intervals. Candle storage and cache keys use an unrestricted
timeframe string, so they require no schema change.

## Goals / Non-Goals

**Goals:**

- Make canonical `4h` requests valid for every enabled symbol in historical, stream, and backfill
  paths.
- Use a 240-minute duration and the existing UTC epoch-aligned fixed-duration behavior.
- Preserve provider routing, market-session filtering, range semantics, serialization, caching, and
  persistence behavior.

**Non-Goals:**

- Supporting `h4` or other aliases.
- Detecting provider interval capabilities at startup or request time.
- Aggregating smaller candles, remapping symbols, or falling back to another provider.
- Adding configuration, dependencies, or database migrations.

## Decisions

### Extend the shared timeframe model

Add `4h` with a 240-minute duration and `4h` provider interval to the existing timeframe registry.
All generic range, close-time, schedule, cache, persistence, and backfill code then reuses the
current fixed-duration path. A separate four-hour type or service would duplicate existing behavior.

### Map `4h` directly at provider boundaries

Add the provider-specific four-hour identifier to each retained REST adapter and to the Binance
WebSocket kline map. The gateway will not probe provider capabilities or aggregate `1h` candles.
Provider rejection continues through the existing sanitized provider-unavailable boundary.

### Reuse tick-derived stream candles

Add `4h` to downstream stream validation. Twelve Data and yfinance already derive candle buckets
from the shared duration registry, so no provider-specific four-hour stream implementation is
needed for those adapters.

### Preserve current session and timestamp rules

Four-hour schedules use the existing UTC fixed-duration grid, and market-session policies treat
`4h` as intraday. REST adapters continue preserving valid upstream open timestamps according to
their current normalization contracts.

## Risks / Trade-offs

- [A provider rejects its configured four-hour interval] → Return the existing sanitized
  provider-unavailable response; capability probing and aggregation remain out of scope.
- [A four-hour bucket overlaps a market close or break] → Preserve the existing rule that eligibility
  is determined from the candle open time, matching other intraday timeframes.
- [REST provider timestamps differ from the UTC stream grid] → Preserve current provider-authoritative
  REST timestamp semantics rather than introducing timeframe-specific shifting.

## Migration Plan

Deploy the additive application and documentation change with no database migration. Existing rows,
clients, and timeframes remain valid. Rollback removes `4h` from validation and provider maps;
already persisted `4h` rows remain inert and can be retained.

## Open Questions

None. Direct provider mapping without capability checks or aggregation is an explicit scope
decision.
