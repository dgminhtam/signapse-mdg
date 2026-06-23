## Context

The gateway already routes persisted `TWELVE_DATA` symbols through one REST adapter and one shared
WebSocket adapter. Despite their Forex-oriented class and constant names, those adapters already
serve XAU/USD and four US stocks in addition to Forex. Their hard-coded allowlist currently blocks
WTI, SPY, and QQQ even if registry rows are added.

The current market-session selector has only two outcomes: the Forex weekly session or always open.
That fallback is unsuitable for SPY/QQQ and causes historical gap detection, stream stale detection,
cache writes, and persistence to treat closed exchange periods as expected trading slots. WTI also
needs an explicit weekly energy session so weekend and daily maintenance periods are not repeatedly
requested or synthesized.

The user has validated that Twelve Data accepts provider symbols `WTI`, `SPY`, and `QQQ`.

## Goals / Non-Goals

**Goals:**

- Add enabled registry mappings for WTI, SPY, and QQQ.
- Serve all three through existing HTTP quote, HTTP candle, and WebSocket contracts.
- Generalize Twelve Data adapter terminology and allowlisting without leaking SDK types.
- Add deterministic, timezone-aware ETF and WTI market-session policies.
- Preserve natural provider gaps and existing provider-agnostic response/event shapes.
- Keep one process-local Twelve Data WebSocket connection shared across supported Twelve Data
  instruments.

**Non-Goals:**

- Do not add XAG/USD, BRENT, SPX, NDX, DJI, natural gas, or agricultural commodities.
- Do not model exchange holidays, shortened sessions, emergency closures, or provider maintenance
  incidents beyond WTI's normal daily maintenance break.
- Do not add automatic provider fallback, exchange-qualified canonical symbols, or extended-hours
  selection as a public API option.
- Do not change the public timeframe set or response field shapes.
- Do not replace the official `twelvedata` SDK.

## Decisions

### Seed the validated symbols with explicit asset classes

Add one migration after `20260622_0006` with these rows:

| Canonical symbol | Asset class | Provider | Provider symbol |
| --- | --- | --- | --- |
| `WTI` | `COMMODITY` | `TWELVE_DATA` | `WTI` |
| `SPY` | `ETF` | `TWELVE_DATA` | `SPY` |
| `QQQ` | `ETF` | `TWELVE_DATA` | `QQQ` |

The migration uses the existing PostgreSQL upsert pattern keyed by canonical symbol. Downgrade
deletes only rows that still match all values introduced by the migration.

Alternative considered: classify SPY and QQQ as `US_STOCK`. That avoids a new asset-class value but
loses product taxonomy already defined in `docs/assets.md` and makes future ETF-specific behavior
harder to express.

### Generalize the existing Twelve Data adapters instead of adding parallel adapters

Rename Forex-specific adapter classes, factories, constants, protocols, tests, and dependency
providers to describe Twelve Data instruments generally. Keep one REST client and one WebSocket
connection because the SDK operations and normalized gateway models are shared.

Use an explicit repository-owned allowlist containing every enabled Twelve Data provider symbol.
Provider discovery remains a validation aid and is not required during application startup.

Alternative considered: add separate ETF and commodity adapters. That would duplicate SDK client
locking, payload normalization, error mapping, connection lifecycle, subscriptions, and event
bridging while still targeting the same provider and WebSocket endpoint.

### Use persisted asset class to select normalization and session behavior

The adapter continues to normalize price and OHLC values uniformly. Volume handling becomes
asset-aware:

- Preserve valid provider volume for SPY and QQQ.
- Accept absent/null volume as decimal zero for WTI and the existing instruments where the
  provider does not supply usable volume.
- Reject malformed, negative, or non-finite supplied volume for every asset.

The `SupportedSymbol.asset_class` value selects market-session policy at service and stream
boundaries; provider symbol spelling does not determine policy.

### Define SPY and QQQ as regular-session US ETFs

ETF intraday candle slots are eligible Monday through Friday from 09:30 inclusive to 16:00
exclusive in `America/New_York`. ETF `1d` candles use Monday-through-Friday UTC date labels.

Quotes may still be emitted when Twelve Data supplies valid extended-hours prices, but candle
generation, missing-range calculation, cache exposure, and persistence use the regular-session
policy. This keeps one deterministic candle contract without adding a public extended-hours mode.

Alternative considered: include pre-market and post-market. Twelve Data entitlement and extended
hours availability can differ by plan, and the current API has no session selector. Regular hours
are the least surprising stable default.

### Define WTI using a pragmatic New York energy session

WTI intraday slots are eligible Sunday 18:00 inclusive through Friday 17:00 exclusive in
`America/New_York`, excluding the recurring 17:00 inclusive to 18:00 exclusive daily maintenance
window Monday through Thursday. WTI `1d` candles accept Monday-through-Friday UTC date labels.

This policy matches the common electronic WTI trading week closely enough to prevent weekend and
maintenance slots from becoming false gaps. Holidays and exceptional schedules remain outside the
current policy model.

Alternative considered: leave WTI always open and preserve provider gaps. The candle service would
then repeatedly identify closed-session slots as missing and issue unnecessary provider requests.

### Reuse the shared Twelve Data price stream and derived candle builder

WTI, SPY, and QQQ subscriptions use the existing shared Twelve Data quote WebSocket. Valid price
events produce normalized quote events. The gateway derives candle events from price ticks using
the existing bucket builder, but applies the symbol's ETF or WTI policy before emitting, caching,
or persisting a candle.

`MARKET_CLOSED` remains provider-agnostic and applies to closed ETF and WTI candle interests in the
same way it applies to Forex candle interests. No upstream OHLC WebSocket dependency is introduced.

## Risks / Trade-offs

- **WTI provider session can differ from the pragmatic energy schedule** → Keep the policy isolated
  by asset class, test its boundaries, and document that holidays and provider-specific exceptions
  are not modeled.
- **SPY/QQQ quotes may arrive outside regular candle hours** → Keep quote and candle channel status
  independent; only candle interests become `MARKET_CLOSED`.
- **Renaming provider code creates broad mechanical churn** → Preserve behavior through compatibility
  aliases only where needed during the refactor and run the full regression suite.
- **Twelve Data plan entitlements may differ between REST and WebSocket** → Map live failures to
  sanitized `PROVIDER_UNAVAILABLE` behavior without affecting other provider groups.
- **ETF daily timestamps may reflect exchange/provider labeling** → Normalize to the existing UTC
  contract and test provider payload fixtures for both symbols.

## Migration Plan

1. Generalize Twelve Data adapter naming and expand its allowlist with regression tests.
2. Add ETF and WTI market-session policies and boundary tests.
3. Add the idempotent registry migration for WTI, SPY, and QQQ.
4. Extend REST and WebSocket tests for routing, normalization, market closure, cache, and
   persistence.
5. Update OpenSpec main specs and public documentation.
6. Deploy the application code and migration together, then run `alembic upgrade head`.
7. Verify `/v1/symbols`, latest quotes, representative candle windows, and one WebSocket
   subscription for each new symbol.

Rollback disables or removes the three registry mappings first, then reverts the application.
Migration downgrade is safe only while the rows still match the seeded mappings.

## Open Questions

None blocking. Extended-hours ETF candles and exchange-holiday calendars can be proposed
separately if product needs them.
