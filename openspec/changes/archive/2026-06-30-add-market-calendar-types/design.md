## Context

`add-market-calendar-tables` introduced `market_calendars`, `market_calendar_sessions`, and nullable
`supported_symbols.calendar_code`. It deliberately seeded only `FOREX_24_5` and `US_REGULAR` and
deferred the calendar dependency.

This change fills the next smallest gap: install the calendar package and seed type rows/mappings.
It still does not generate session rows or alter market-data request behavior.

## Goals / Non-Goals

**Goals:**

- Add `pandas-market-calendars` as a pinned project dependency.
- Seed calendar definitions for all supported asset groups that need a persisted calendar type.
- Map symbols to calendar codes using current provider/proxy symbols.
- Leave uncertain mappings explicit and easy to revisit.

**Non-Goals:**

- Do not call `pandas_market_calendars.get_calendar()` or generate sessions.
- Do not add a CLI, scheduler, refresh job, or backfill process.
- Do not change `MarketSessionPolicy`, candle gap detection, quotes, streams, or public schemas.
- Do not store candle opens.

## Decisions

### Seed calendar types separately from generated sessions

The migration should add/update `market_calendars` rows only. `generated_from` and `generated_to`
remain null until a later session-generation change writes actual coverage.

Alternative considered: generate sessions immediately after adding the package. That mixes seed data
with runtime calendar semantics and makes validation larger than needed.

### Keep calendar codes product-oriented

Use stable internal codes:

```text
CRYPTO_24_7
FOREX_24_5
US_REGULAR
CME_ENERGY
CME_METALS
CME_AGRICULTURE
ICE_SOFTS
```

This keeps canonical assets decoupled from provider symbols while still reflecting their current
market calendar family.

Alternative considered: one generic `CME_FUTURES` code. That is shorter but hides product-session
differences that matter for energy, metals, and agriculture.

### Map current supported symbols conservatively

Map obvious assets:

- crypto pairs -> `CRYPTO_24_7`
- Forex pairs and Twelve Data spot gold -> `FOREX_24_5`
- US stocks, ETFs, and US stock indexes -> `US_REGULAR`
- WTI, Brent, natural gas -> `CME_ENERGY`
- silver futures proxy `SI=F` -> `CME_METALS`
- wheat and corn futures proxies -> `CME_AGRICULTURE`
- coffee and sugar futures proxies -> `ICE_SOFTS`

Alternative considered: leave all futures unmapped until a live provider comparison. That avoids
wrong precision, but it delays the only data decision this change is meant to capture. Generation
and runtime usage remain deferred, so mappings are cheap to adjust before they matter.

## Risks / Trade-offs

- pandas-market-calendars calendar names can differ from internal codes -> Store package calendar
  names in `source_calendar` and cover them with seed tests.
- Some futures proxies may use exchange calendars more specific than our first mapping -> Keep
  generation and runtime use deferred until a spike compares provider gaps.
- `CRYPTO_24_7` is not a package-provided exchange calendar -> Store it as an internal calendar
  source, not a pandas source.
- Dependency upgrades can change holiday data -> Pin the dependency and treat upgrades as calendar
  data changes.

## Migration Plan

1. Add the pinned `pandas-market-calendars` dependency with `uv`.
2. Add an Alembic seed migration after the calendar-table migration.
3. Upsert calendar type rows and update existing supported symbol mappings.
4. Add focused tests proving dependency availability, calendar rows, and symbol mappings.
5. Downgrade removes only rows/mappings introduced by this change where safe.
