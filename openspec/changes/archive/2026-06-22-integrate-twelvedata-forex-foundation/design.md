## Context

The gateway currently has a working Binance Spot provider foundation for crypto quotes, candles,
and WebSocket streams. `docs/assets.md` now lists four Forex pairs as current product catalog
coverage: `EUR/USD`, `GBP/USD`, `USD/JPY`, and `AUD/USD`. Massive was evaluated as a Forex data
candidate, but live quote access requires a paid entitlement. Twelve Data is a lower-cost
candidate for the Forex bootstrap because its SDK supports Forex time series, quote/price
requests, and symbol discovery using canonical pair strings such as `EUR/USD`.

This change deliberately stops before public Forex API enablement. It prepares the dependency,
configuration, provider boundary, and registry seed so a later change can route quote/candle
requests to Twelve Data with less uncertainty.

## Goals / Non-Goals

**Goals:**

- Add the official `twelvedata` Python SDK as the Forex provider dependency.
- Keep Twelve Data SDK clients, request builders, payloads, and exceptions inside
  `app/providers/`.
- Add typed settings for Twelve Data API key, REST base URL, and timeout policy.
- Add a Twelve Data Forex adapter foundation that can validate provider symbols and normalize
  REST price/time-series payloads in provider-owned tests.
- Seed the four current Forex catalog pairs into `supported_symbols` as enabled `FOREX` records.
- Preserve all existing Binance crypto behavior.

**Non-Goals:**

- Do not route public `/v1/quotes` requests to Twelve Data yet.
- Do not route public `/v1/candles` requests to Twelve Data yet.
- Do not implement or wire Twelve Data WebSocket streaming.
- Do not synthesize realtime Forex candles from price ticks.
- Do not add provider fallback, aggregation, or cross-provider routing policies beyond the
  minimal foundation needed for a later change.

## Decisions

### Use Twelve Data SDK for the Forex foundation

Twelve Data provides an official Python client with Forex OHLC time series, quote/price endpoints,
Forex pair listing, and WebSocket support. For this change, only REST-oriented SDK surfaces are
prepared. This keeps the provider decision aligned with the repository guideline to prefer
official SDKs when viable.

Alternative considered: direct HTTP calls to Twelve Data. Direct calls would give tighter async
control, but would bypass the provider integration guideline and duplicate behavior already
represented by the SDK.

Alternative considered: Massive Forex. Massive appears to support the target pairs, but the
current API key is not entitled to quote data. Twelve Data is preferred for a cost-conscious first
Forex provider.

### Keep the SDK behind a narrow adapter boundary

The adapter will expose repository-owned methods for provider symbol validation, latest price
fetching, and candle/time-series normalization. Domain, service, cache, API, and repository modules
must not import Twelve Data SDK types.

The Twelve Data SDK uses synchronous `requests` for REST. Adapter calls that perform SDK network
I/O will run outside the ASGI event loop and will serialize access to any shared SDK client,
matching the existing Binance SDK pattern.

### Store Twelve Data provider symbols as canonical pair strings

The registry will map:

```text
EUR/USD -> TWELVE_DATA:EUR/USD
GBP/USD -> TWELVE_DATA:GBP/USD
USD/JPY -> TWELVE_DATA:USD/JPY
AUD/USD -> TWELVE_DATA:AUD/USD
```

This keeps canonical and provider symbols identical for Forex while still retaining provider
replaceability through the registry.

### Add a new migration for Forex seeds

The existing initial registry migration seeds crypto MVP symbols. This change should add a new
idempotent migration that inserts or updates the Forex rows without changing the original crypto
seed semantics.

Rollback should remove only rows introduced by the Forex seed migration when they still match
the `TWELVE_DATA` provider mapping.

### Defer public API routing

Seeding Forex symbols means `/v1/symbols` can list them once migrations are applied, but public
quote/candle services must not start calling Twelve Data in this change. Existing quote/candle
services are still Binance-backed and a later provider-routing change must explicitly decide how
to dispatch by provider and asset class.

## Risks / Trade-offs

- **Twelve Data SDK is synchronous** → Run SDK work through the adapter outside the event loop and
  test that the SDK does not leak past `app/providers/`.
- **Free/Basic plan limits are tight** → Keep live provider smoke tests opt-in and do not depend
  on Twelve Data availability for the default test suite.
- **WebSocket access may require a higher plan** → Keep WebSocket out of scope and do not promise
  realtime Forex streaming in this change.
- **Forex `volume` semantics may differ from crypto** → Avoid public candle routing until the
  later API change defines Forex candle semantics explicitly.
- **Registry lists Forex before data APIs support it** → Document that this is a foundation change
  and ensure quote/candle behavior remains unchanged until provider routing is implemented.

## Migration Plan

1. Add `twelvedata` to locked project dependencies.
2. Add Twelve Data configuration keys to typed settings and environment examples.
3. Add provider adapter foundation and tests with fake SDK/client boundaries.
4. Add an Alembic migration that seeds the four Forex symbols idempotently.
5. Update documentation to describe Twelve Data as the selected low-cost Forex REST foundation.
6. Verify existing crypto behavior still passes.

Rollback:

- Revert the dependency/config/provider changes.
- Downgrade the Forex seed migration; it should remove only the seeded `TWELVE_DATA` Forex rows.

## Open Questions

- Which exact `twelvedata` package version should be locked after dependency resolution under
  Python 3.14?
- Should the later Forex API-routing change use Twelve Data `price()` or `quote()` for latest
  quotes when both are available?
- Should Forex historical candles expose Twelve Data `volume` directly, convert missing volume to
  `0`, or document a Forex-specific activity-volume interpretation?
