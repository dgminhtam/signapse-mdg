## Context

The previous calendar schema introduced reusable `market_calendars`, generated
`market_calendar_sessions`, and `supported_symbols.calendar_code`. Further exploration showed that
`pandas_market_calendars` uses local package rules rather than fetching calendars from a remote
service, so materializing sessions is not needed for the next runtime-filtering step.

## Goals / Non-Goals

**Goals:**

- Store calendar source metadata directly on supported symbols.
- Remove the calendar definition/session tables from the intended schema.
- Keep the change limited to schema, model, seed, and tests.

**Non-Goals:**

- Do not filter candles with `pandas_market_calendars`.
- Do not add a scheduler, CLI, refresh job, or generated session persistence.
- Do not change public API response shapes.

## Decisions

- Inline calendar config on `supported_symbols` using nullable `calendar_source`,
  `calendar_name`, and `calendar_timezone`.
  - Alternative considered: keep a `market_calendars` type table and FK from symbols.
  - Rationale: no current admin/API/reporting workflow needs reusable calendar rows, and avoiding
    the join keeps the schema smaller.
- Drop `market_calendar_sessions`.
  - Alternative considered: precompute sessions in a scheduler.
  - Rationale: the calendar package is local and request ranges are already bounded, so session
    materialization is deferred until audit, override, or measured performance needs exist.
- Keep `pandas-market-calendars` as the pinned source dependency.
  - Alternative considered: defer the dependency again.
  - Rationale: the next runtime-filtering change can use the already-pinned local calendar rules.

## Risks / Trade-offs

- Duplicate calendar config values across symbols -> acceptable until calendar type management
  becomes a real workflow.
- No FK validation for calendar names -> cover with seed tests and a dependency import test; runtime
  validation belongs to the later filtering change.
- Dropping materialized sessions removes an audit path -> add persistence later only if audit,
  manual override, or performance pressure appears.
