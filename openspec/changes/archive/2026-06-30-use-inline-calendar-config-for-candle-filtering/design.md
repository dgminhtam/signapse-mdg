## Context

Historical candles, REST provider normalization, stream candle derivation, stream market-closed
state, cache merge, and persistence handoff already route through `get_market_session_policy()` and
`policy.is_eligible()`. The prior inline calendar-config change adds nullable calendar metadata to
`supported_symbols`, but runtime `SupportedSymbol` values do not yet carry or use it.

## Goals / Non-Goals

**Goals:**

- Load inline calendar config into internal `SupportedSymbol` values.
- Use existing market-session policy callsites for historical and stream candle eligibility.
- Use `pandas_market_calendars` for exchange calendars with local cached schedules.
- Preserve the existing internal always-open and Forex weekly-session policies where they are the
  correct runtime source.

**Non-Goals:**

- Do not add calendar session persistence, a scheduler, CLI refresh, or background jobs.
- Do not change public response shapes.
- Do not refactor provider routing or candle storage.

## Decisions

- Keep `MarketSessionPolicy`.
  - Alternative considered: inject a separate calendar service into candle service, providers, and
    stream manager.
  - Rationale: existing code already has one eligibility boundary; replacing the implementation is
    the smallest safe change.
- Add nullable calendar fields to the domain `SupportedSymbol` dataclass and repository mapping.
  - Alternative considered: query symbol calendar config separately inside policy creation.
  - Rationale: symbol lookup already precedes all relevant candle work.
- Use an `lru_cache` around calendar objects and short schedule lookups.
  - Alternative considered: materialize schedules in PostgreSQL.
  - Rationale: request ranges are bounded and `pandas_market_calendars` rules are local package data.
- Treat `internal:24/7` as always open and keep Forex/XAU on the existing weekly quote-session
  policy for this change.
  - Alternative considered: use `pandas_market_calendars` `FOREX` directly.
  - Rationale: the package `FOREX` calendar can expose a Saturday-open session for the tested week;
    the existing internal Forex policy matches the gateway contract.
- For pandas calendars:
  - Intraday opens are eligible inside `market_open <= open_time < market_close`.
  - Break windows exclude `break_start <= open_time < break_end`.
  - Daily labels are eligible when the UTC open date is a calendar session date.
  - Weekly/monthly labels are eligible when the requested period contains at least one calendar
    session.

## Risks / Trade-offs

- Package calendars may not match every provider proxy exactly -> keep internal fallback and add
  tests for current supported mappings.
- Schedule lookup per candidate open can be wasteful -> `lru_cache` keeps this acceptable; revisit
  only if profiling shows it matters.
- Forex remains internal while other calendars use pandas -> explicit tests document the exception.

## Migration Plan

No database migration is needed in this change. It depends on `inline-symbol-calendar-config` being
applied first.
