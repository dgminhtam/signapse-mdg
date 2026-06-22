## Context

Signapse currently accepts every valid Twelve Data Forex time-series row inside the requested
half-open UTC range. Twelve Data can emit indicative hourly candles continuously through Saturday
and Sunday, while common broker/MT5 charts contain bars only while the broker's Forex quote session
is open.

The historical candle service currently treats every aligned timeframe slot as expected. It reads
all persisted rows, marks every absent slot as a provider gap, fetches those contiguous gaps, and
then persists every completed normalized row. Therefore filtering only at the API response would
still store weekend candles and repeatedly request closed-session gaps.

The current supported Forex catalog has one common asset class (`FOREX`) and one provider
(`TWELVE_DATA`). The solution should nevertheless describe Signapse market semantics independently
of provider quirks and remain reusable for future Forex providers.

## Goals / Non-Goals

**Goals:**

- Define the Signapse Forex weekly quote session as Sunday 17:00 through Friday 17:00 in
  `America/New_York`.
- Apply daylight-saving changes automatically.
- Avoid requesting, returning, caching, or persisting Forex candles whose open time is outside the
  weekly quote session.
- Preserve open-session gaps when providers omit real data; do not synthesize candles.
- Remove already persisted closed-session Forex candles.
- Keep all non-Forex candle behavior unchanged.

**Non-Goals:**

- Do not model holidays, early closes, late opens, emergency closures, or provider maintenance.
- Do not change latest quote behavior.
- Do not change WebSocket subscriptions or stream event filtering.
- Do not add market-session fields to the supported-symbol registry.
- Do not change public candle request or response fields.
- Do not implement provider-specific session discovery.

## Decisions

### Introduce a domain-owned market session policy

Add a small repository-owned policy boundary that answers whether a candle open time is eligible
and can enumerate eligible open ranges or slots for a requested interval.

The initial policies are:

```text
AlwaysOpenSessionPolicy
ForexWeeklySessionPolicy
```

Policy selection is based on persisted `asset_class`: `FOREX` selects the Forex policy and all
other current classes select always-open behavior.

This expresses Signapse chart semantics independently from Twelve Data and lets the service,
provider normalization, persistence cleanup, and future providers share one definition.

Alternative considered: put weekday checks directly in the Twelve Data adapter. That would stop
some invalid rows but would not prevent the service from requesting closed ranges or returning old
invalid persisted rows.

### Use America/New_York local wall time for the weekly boundary

The Forex session is:

```text
open:  Sunday 17:00 America/New_York
close: Friday 17:00 America/New_York
```

Use `zoneinfo.ZoneInfo("America/New_York")` with the `tzdata` package as the portable IANA
database. The policy converts each UTC candle open time to New York local time before evaluating
the weekday and local time.

This naturally produces approximately 21:00 UTC boundaries during EDT and 22:00 UTC boundaries
during EST.

Alternative considered: hardcode UTC boundaries. That would be wrong during half of the year and
around daylight-saving transitions.

### Define intraday eligibility by candle open time

For `1m`, `5m`, `15m`, and `1h`, a candle is eligible when its `open_time` lies in the weekly quote
session. A candle opening exactly Friday 17:00 New York is excluded. A candle opening exactly
Sunday 17:00 New York is included.

This matches the gateway's existing candle identity and half-open range model.

### Treat daily candles separately

Twelve Data labels current `1d` rows at UTC day boundaries rather than at the Sunday/Friday
intraday session boundary. For `1d`, Signapse will retain rows labeled Monday through Friday in UTC
and exclude rows labeled Saturday or Sunday.

This is intentionally a pragmatic chart rule. Applying the 17:00 New York instant rule to
`open_time=00:00Z` daily labels would misclassify valid trading days.

Alternative considered: disable session filtering for daily candles. That would still permit
weekend daily bars if the provider emits them.

### Make service gap detection session-aware

After resolving the registry symbol, the service selects its session policy and:

1. Removes persisted rows whose open time is ineligible.
2. Finds missing slots only among eligible slots.
3. Coalesces adjacent eligible missing slots into provider ranges.
4. Filters provider results again before completion calculation and persistence.
5. Filters a current cached candle before merging it into the response.

For a request spanning a weekend, provider calls are split around the closed interval. For a range
containing only closed-session Forex slots, no provider request is made and an empty candle list is
returned.

### Keep provider defense in depth

The Twelve Data adapter should use the same Forex session policy to discard closed-session rows
before returning normalized candles. The service remains the authoritative cross-provider guard,
while the adapter prevents provider-specific invalid rows from crossing its boundary.

Alternative considered: service-only filtering. Correctness would be preserved today, but the
adapter could still appear to normalize known ineligible Forex data when tested or reused directly.

### Clean existing rows with a targeted Alembic migration

Add a data-only migration that deletes `market_data_candles` rows where `asset_class = 'FOREX'` and:

- intraday open time falls in Friday 17:00 through Sunday 17:00 New York local time; or
- timeframe is `1d` and UTC weekday is Saturday or Sunday.

The cleanup must leave crypto and other asset classes untouched. Downgrade cannot reconstruct
deleted indicative candles and is therefore a documented no-op.

Even after cleanup, runtime filtering remains required to protect against later imports or provider
behavior changes.

## Risks / Trade-offs

- **Forex OTC venues can quote outside the chosen weekly session** → Treat this explicitly as a
  Signapse chart policy, not a claim that no indicative quote exists.
- **DST transition weeks are easy to mishandle** → Use `zoneinfo` in runtime tests and PostgreSQL
  `AT TIME ZONE 'America/New_York'` semantics in cleanup tests.
- **Daily candle timestamp semantics differ from intraday** → Use the explicit weekday-label rule
  and cover it independently.
- **Data migration deletes historical rows irreversibly** → Restrict deletion to `FOREX` and the
  exact weekly closed-session predicate; downgrade is a no-op.
- **Enumerating every minute slot could be expensive** → Requests are already capped at 1,000
  slots; use range coalescing and avoid provider calls for closed ranges.
- **Holidays remain visible if the provider emits candles** → Document this deliberate limitation;
  a separate override-calendar capability can be added if product requirements change.

## Migration Plan

1. Deploy runtime session policy and service/provider filtering.
2. Run the targeted Alembic cleanup migration.
3. Re-request a range spanning Friday through Monday and verify that only open-session candles are
   returned and persisted.
4. Verify crypto ranges remain continuous and unchanged.

Rollback can revert runtime filtering, but deleted weekend Forex rows are not restored. They can be
refetched from the provider if Signapse later chooses indicative 24/7 Forex charts.

## Open Questions

- None for this scope. Holiday and exceptional-session support is intentionally deferred.
