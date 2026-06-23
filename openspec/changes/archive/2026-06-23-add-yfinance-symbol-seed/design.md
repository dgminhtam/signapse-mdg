## Context

The gateway already has provider-backed registry rows for crypto through Binance Spot and for the
current Forex, metal, stock, WTI, and ETF coverage through Twelve Data. `docs/assets.md` also lists
planned assets that currently have no provider mapping: silver, Brent crude, three stock indexes,
natural gas, coffee, sugar, wheat, and corn.

yfinance can supply Yahoo Finance ticker data for these planned assets, but it is not an official
Yahoo SDK. It is an open-source wrapper over public Yahoo Finance APIs, and its own documentation
frames usage around Yahoo's terms and personal/research use. This change therefore introduces it
only as a dependency and registry provider candidate, leaving runtime market-data calls for a later
change after product and operational validation.

## Goals / Non-Goals

**Goals:**

- Add the yfinance package to the project dependency set with an exact lockfile entry.
- Seed all currently unbacked planned assets as enabled registry rows mapped to provider
  `YFINANCE`.
- Add `STOCK_INDEX` as a public registry asset class for index rows.
- Preserve all existing Binance and Twelve Data registry mappings.
- Keep public quote, candle, and WebSocket routing unchanged.
- Make proxy semantics explicit for yfinance commodity symbols that represent futures contracts.

**Non-Goals:**

- Do not implement a yfinance REST adapter for latest quotes or historical candles.
- Do not wire yfinance into quote provider routing, candle provider routing, or stream provider
  routing.
- Do not implement yfinance WebSocket usage.
- Do not replace existing Binance or Twelve Data coverage.
- Do not solve spot-metal coverage for `XAG/USD`; this change seeds the Yahoo Finance silver
  futures proxy `SI=F`.
- Do not model exchange holidays, futures roll schedules, contract expiration behavior, or index
  market sessions yet.

## Decisions

### Use a new `YFINANCE` provider identifier

Seed the new rows with provider `YFINANCE` rather than overloading `TWELVE_DATA` or adding a generic
`YAHOO_FINANCE` string. The provider identifier should match the dependency and future adapter
boundary, making it clear which integration owns the provider symbols.

Alternative considered: use `YAHOO_FINANCE`. That is more descriptive of the upstream data source,
but yfinance is not affiliated with Yahoo and the code dependency will be named `yfinance`, so
`YFINANCE` keeps the repository boundary honest.

### Seed only assets that do not already have a provider

The migration should add the ten unbacked planned assets and should not touch existing Binance or
Twelve Data rows. That keeps the first yfinance experiment isolated to catalog expansion instead of
changing data behavior for currently supported symbols.

| Canonical symbol | Asset class | Provider | Provider symbol | Notes |
| --- | --- | --- | --- | --- |
| `XAG/USD` | `COMMODITY` | `YFINANCE` | `SI=F` | Silver futures proxy |
| `BRENT` | `COMMODITY` | `YFINANCE` | `BZ=F` | Brent crude futures |
| `SPX` | `STOCK_INDEX` | `YFINANCE` | `^GSPC` | S&P 500 index |
| `NDX` | `STOCK_INDEX` | `YFINANCE` | `^NDX` | NASDAQ-100 index |
| `DJI` | `STOCK_INDEX` | `YFINANCE` | `^DJI` | Dow Jones Industrial Average |
| `NATGAS` | `COMMODITY` | `YFINANCE` | `NG=F` | Natural gas futures |
| `COFFEE` | `COMMODITY` | `YFINANCE` | `KC=F` | Coffee futures |
| `SUGAR` | `COMMODITY` | `YFINANCE` | `SB=F` | Sugar #11 futures |
| `WHEAT` | `COMMODITY` | `YFINANCE` | `ZW=F` | Chicago SRW wheat futures |
| `CORN` | `COMMODITY` | `YFINANCE` | `ZC=F` | Corn futures |

Alternative considered: include `BTC-USD`, `ETH-USD`, or existing stocks/ETFs in the yfinance seed.
That would create provider overlap before fallback or priority rules exist, so it is deferred.

### Add `STOCK_INDEX` instead of mapping indexes as ETFs or commodities

`SPX`, `NDX`, and `DJI` are not tradable ETFs and should not inherit ETF semantics from `SPY` or
`QQQ`. A new `STOCK_INDEX` asset class keeps product taxonomy clear and avoids encoding index
behavior into provider symbols.

Alternative considered: map indexes as `ETF` using proxy ETFs. That would make data easier to trade
against but would mislabel the catalog assets product wants to expose.

### Add dependency now, adapter later

This change should add yfinance to the locked project dependencies and test that imports stay out
of domain, API, service, cache, and database layers. No yfinance client should be created during
application startup, and no route should invoke yfinance until a later provider-routing proposal
defines quote/candle behavior, timeouts, sessions, and failure mapping.

Alternative considered: add the dependency and a skeleton provider adapter now. That creates more
surface area without any public route using it, and risks choosing adapter contracts before the
runtime semantics are designed.

## Risks / Trade-offs

- yfinance is not an official Yahoo SDK and Yahoo Finance data usage has terms restrictions -> Keep
  this phase limited to dependency and registry seeding, and document the operational/legal caveat
  before any market-data routing.
- Futures symbols are proxies for several commodity canonicals -> Mark the mapping in design/docs
  and avoid presenting them as spot instruments in provider-facing decisions.
- Enabled registry rows can appear in `/v1/symbols` before data routes are implemented -> Make the
  no-routing behavior explicit and test that yfinance is not called by quote, candle, or WebSocket
  paths in this change.
- `STOCK_INDEX` expands the public asset-class set -> Update symbol DTO validation, docs, and tests
  together with the seed migration.
- Yahoo symbols containing `^` and `=` are provider symbols, not canonical symbols -> Keep them only
  in registry/provider fields and ensure clients continue using canonical symbols.

## Migration Plan

1. Add and lock the yfinance dependency without introducing runtime imports outside provider-owned
   code.
2. Extend any asset-class validation to include `STOCK_INDEX`.
3. Add an Alembic revision after the current supported-symbol seed revisions that idempotently
   upserts the ten `YFINANCE` rows.
4. Update symbol registry tests, migration tests, and public symbol documentation.
5. Verify existing quote, candle, and stream tests still prove no yfinance market-data routing was
   added.
6. Deploy the dependency and migration together, then run `alembic upgrade head`.

Rollback should downgrade the migration only for rows that still match the seeded `YFINANCE`
mappings. Removing the dependency is safe while no runtime adapter imports yfinance.

## Open Questions

- Should `XAG/USD` remain a spot-style canonical while using `SI=F`, or should product rename it to
  a futures-specific canonical before public data routing?
- Should futures roll metadata eventually be exposed internally for commodities, or is the Yahoo
  continuous/rolling symbol acceptable for the first data-serving phase?
