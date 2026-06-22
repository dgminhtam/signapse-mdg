## Context

`GET /v1/candles` already validates one canonical symbol and timeframe, reads complete candles
from PostgreSQL, fetches missing contiguous ranges, persists newly completed candles, and returns
a provider-agnostic response. Its dependency wiring currently constructs only a Binance candle
provider even though the enabled registry now includes four `TWELVE_DATA` Forex mappings.

The Twelve Data adapter foundation already exposes `fetch_candles` through the repository-owned
`CandleProvider` shape and maps the public timeframes to Twelve Data intervals. The remaining work
is provider dispatch, optional credential handling, and stronger normalization of provider range
and volume semantics.

Unlike quotes, one candle request contains only one symbol. Routing therefore does not require
batch grouping or partial provider outcomes. Forex also differs from 24/7 crypto because expected
UTC timeframe slots can legitimately be absent while the market is closed.

## Goals / Non-Goals

**Goals:**

- Route candle cache misses by the enabled symbol's persisted `provider`.
- Serve historical candles for the four seeded Forex pairs through Twelve Data.
- Preserve Binance crypto candle behavior and the existing public candle contract.
- Preserve PostgreSQL-first gap fill and the current provider-specific candle identity.
- Adapt the gateway's half-open range to Twelve Data request semantics.
- Normalize absent Forex volume to exact decimal zero.
- Keep startup and crypto candles usable when Twelve Data credentials are absent.
- Preserve natural provider gaps without synthesizing candles.

**Non-Goals:**

- Do not add Forex or Twelve Data support to `/v1/stream`.
- Do not add Twelve Data WebSocket integration.
- Do not implement provider fallback, aggregation, or price reconciliation.
- Do not add a market calendar, closed-session table, or persistent negative gap cache.
- Do not add candle fields, change request parameters, or add a database migration.
- Do not claim that zero Forex volume represents measured trading volume.

## Decisions

### Route a single candle request through a provider registry

Introduce a repository-owned candle provider router implementing `CandleProvider`. It receives the
resolved `SupportedSymbol`, looks up the concrete provider by `symbol.provider`, and delegates the
existing request unchanged.

This keeps route and service layers independent of provider names while allowing the service to
retain its current repository-first algorithm.

Alternative considered: branch directly inside `routes_candles.py` or `CandleService`. That would
couple API/service behavior to provider names and duplicate the routing pattern already established
for latest quotes.

### Register Twelve Data only when usable configuration exists

The candle route dependency always registers Binance and conditionally registers Twelve Data when
`TWELVEDATA_API_KEY` contains a usable value. A missing router entry raises the sanitized
provider-unavailable boundary only when an affected Forex request needs a provider fill.

This allows application startup, persisted Forex reads, and crypto candle requests to remain
available without a Twelve Data key. A fully persisted Forex range can also be returned without
calling or constructing the provider.

Alternative considered: fail startup when the key is absent. That would turn an optional provider
capability into a process-wide dependency.

### Translate the exclusive gateway end into the last requested candle boundary

The gateway owns `[from,to)` semantics. For Twelve Data, the adapter sends:

```text
start_date = from
end_date = to - timeframe_duration
outputsize = expected gateway slot count
order = ASC
timezone = UTC
```

The adapter still filters normalized rows to `from <= open_time < to`. This avoids relying on an
upstream interpretation of `end_date` and prevents a row opening exactly at `to` from invalidating
an otherwise usable response.

Alternative considered: continue sending `to` and silently drop an extra boundary row. Sending the
last eligible open time expresses the requested range more precisely and avoids spending output
capacity on an ineligible row.

### Treat absent Forex volume as zero, but reject malformed supplied volume

If a Twelve Data Forex row omits `volume` or supplies `null`, the adapter normalizes it to
`Decimal("0")`. If a non-null volume is present, it must remain a finite non-negative decimal.

The public contract already requires `volume` as a decimal string and the database column is
non-null. Zero is therefore the least disruptive provider-neutral placeholder, but documentation
must state that it means “upstream volume unavailable,” not measured zero activity.

Alternative considered: make public and persisted volume nullable. That would be a broader contract
and schema change unrelated to enabling the initial Forex candle path.

### Preserve provider omissions and Forex closed-session gaps

The service continues to return available candles after a fill attempt and does not synthesize
OHLCV rows for missing slots. It also does not persist absence markers in this change.

This preserves current candle semantics and prevents fabricated prices. Repeated requests over
weekends may spend provider quota again; a market-calendar or bounded negative cache can be added
later with explicit expiry semantics.

### Reuse the existing persistence identity

Complete Forex candles use the current unique identity:

```text
(provider, provider_symbol, timeframe, open_time)
```

This naturally separates Twelve Data Forex rows from Binance crypto rows and requires no migration.
Completion remains calculated by the gateway from normalized `close_time` and its receive clock.

## Risks / Trade-offs

- **Twelve Data free-plan quota can be consumed by repeated closed-market gaps** → Keep requests
  bounded and persistence-first; defer a negative cache or market calendar to a focused change.
- **Upstream `end_date` semantics may vary by interval** → Send the last eligible open boundary
  and enforce the gateway range again during normalization.
- **Forex volume zero can be misunderstood** → Document it explicitly as an unavailable-volume
  placeholder and keep the exact decimal representation.
- **The synchronous Twelve Data SDK serializes access** → Continue using `asyncio.to_thread` and
  the adapter lock; acceptable for four initial pairs and bounded requests.
- **A missing key can leave enabled Forex symbols without live fills** → Return stable
  `PROVIDER_UNAVAILABLE` only when persistence cannot satisfy the range.
- **The current global request limits may still be expensive on a free plan** → Reuse the existing
  30-day and 1,000-slot bounds; provider-specific quota tuning can be added later if needed.

## Migration Plan

1. Ensure the existing Forex registry seed migration is deployed.
2. Configure `TWELVEDATA_API_KEY` in environments that should fill live Forex candle gaps.
3. Deploy the candle provider router and hardened Twelve Data normalization.
4. Validate one crypto request, one Forex request, a persisted Forex cache hit, and a weekend range.

Rollback requires reverting the provider routing code. Existing persisted Twelve Data candle rows
can remain because their provider-specific identity does not collide with Binance data.

## Open Questions

- Should a later change add a short-lived negative cache for known-empty provider ranges?
- Should provider-specific request budgets be configurable separately from the public maximum
  range and candle count?
