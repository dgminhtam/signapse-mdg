## ADDED Requirements

### Requirement: Market calendar definitions are persisted

The database SHALL store reusable market calendar definitions keyed by a stable calendar code.

#### Scenario: Calendar definition schema is migrated

- **WHEN** the database is upgraded through this change
- **THEN** a `market_calendars` table exists
- **AND** each row has `code`, `source`, `source_calendar`, `timezone`, `generated_from`,
  `generated_to`, `created_at`, and `updated_at`
- **AND** `code` uniquely identifies the calendar

### Requirement: Market calendar sessions are persisted

The database SHALL store generated trading sessions for each persisted market calendar.

#### Scenario: Calendar session schema is migrated

- **WHEN** the database is upgraded through this change
- **THEN** a `market_calendar_sessions` table exists
- **AND** each row has `calendar_code`, `session_date`, `open_time`, `close_time`, optional
  `break_start`, optional `break_end`, and `created_at`
- **AND** each session references an existing `market_calendars.code`
- **AND** each calendar has at most one session row for a given `session_date`

#### Scenario: Session time constraints are enforced

- **WHEN** a market calendar session row is inserted or updated
- **THEN** the database requires `open_time` to be earlier than `close_time`
- **AND** any break window must have both endpoints and fall strictly inside the session window

### Requirement: Calendar persistence does not change runtime market-data behavior

The market calendar persistence change SHALL NOT change public quote, candle, stream, provider,
or market-session behavior.

#### Scenario: Existing market-data APIs are used after migration

- **WHEN** the database has the new calendar tables and symbol calendar column
- **THEN** existing quote, candle, stream, and symbol API behavior remains unchanged
- **AND** no runtime code reads `market_calendar_sessions` to filter candles in this change

### Requirement: Calendar generation is deferred

The database change SHALL NOT add a calendar generation job, CLI, scheduler, or
pandas-market-calendars dependency.

#### Scenario: Application dependencies are inspected after migration work

- **WHEN** the database-only change is implemented
- **THEN** project dependencies do not include `pandas-market-calendars`
- **AND** no calendar refresh or generation command is required for application startup
