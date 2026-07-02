## Context

Market-session policy is currently code-only. That keeps runtime simple, but it gives the project
no persisted calendar source to seed, inspect, or reuse across symbols before later candle logic
starts using exchange calendars.

This change is intentionally database-only. It creates the minimum schema needed to persist reusable
calendar definitions and generated trading sessions, plus an optional symbol-to-calendar mapping.

## Goals / Non-Goals

**Goals:**

- Add reusable market calendar metadata keyed by a stable `code`.
- Add generated market calendar sessions with UTC open and close timestamps.
- Allow each supported symbol to reference a calendar code when the mapping is known.
- Preserve existing public API behavior and candle-session logic.

**Non-Goals:**

- Do not add pandas-market-calendars as a dependency.
- Do not generate, refresh, or fetch calendar sessions.
- Do not change candle filtering, gap detection, provider routing, or stream behavior.
- Do not store every possible candle open in PostgreSQL.

## Decisions

### Store sessions, not candle opens

Persist one row per trading session in `market_calendar_sessions`. Runtime candle opens can later be
generated from session windows and existing timeframe schedules.

Alternative considered: persist one row per `(calendar, timeframe, open_time)`. That makes queries
simple but creates many rows before there is evidence the project needs that audit level.

### Use calendar codes directly on symbols

Add nullable `supported_symbols.calendar_code` referencing `market_calendars(code)`. A nullable
column keeps crypto and not-yet-verified futures mappings out of the way.

Alternative considered: add a separate symbol-calendar mapping table. There is only one calendar per
symbol in the current model, so an extra table is noise.

### Keep session rows minimal

Store `session_date`, `open_time`, `close_time`, and one optional break window. That covers regular
sessions and simple maintenance breaks without modeling exceptions that are not used yet.

Alternative considered: store JSON schedule payloads. Structured columns are easier to constrain and
query with PostgreSQL.

## Risks / Trade-offs

- A market can have multiple breaks in one day -> Add a child break table when a verified supported
  asset needs it.
- A symbol-calendar mapping may be wrong for a futures proxy -> Leave unverified symbols nullable
  until calendar research confirms the mapping.
- Calendar data can become stale -> Later generation work must own refresh range and source version.
- Existing candle logic will ignore these tables -> Expected in this database-only change.

## Migration Plan

1. Add `market_calendars`.
2. Add nullable `calendar_code` to `supported_symbols`.
3. Add `market_calendar_sessions`.
4. Seed only calendar definition rows and obvious symbol mappings if the existing registry rows
   exist.
5. Downgrade drops the new session table, symbol column, and calendar table.

Rollback is safe for runtime behavior because no application logic reads the new schema yet.
