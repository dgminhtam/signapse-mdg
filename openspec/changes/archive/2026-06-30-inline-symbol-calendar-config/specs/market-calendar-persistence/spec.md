## REMOVED Requirements

### Requirement: Market calendar definitions are persisted

**Reason**: Calendar source metadata is moving inline onto `supported_symbols`, and no current
workflow needs reusable calendar definition rows.
**Migration**: Drop `market_calendars` after adding inline supported-symbol calendar config.

### Requirement: Market calendar sessions are persisted

**Reason**: `pandas_market_calendars` generates schedules from local package rules, so generated
session rows are unnecessary for the scoped schema-only change.
**Migration**: Drop `market_calendar_sessions`; add session persistence later only if audit,
override, or measured performance needs appear.

### Requirement: Calendar persistence does not change runtime market-data behavior

**Reason**: The persistence capability is being retired, so this guard moves to the inline symbol
calendar config and seeding requirements.
**Migration**: Keep runtime quote, candle, stream, provider, and cache behavior unchanged while
adding inline config columns.

### Requirement: Calendar generation is deferred

**Reason**: Generated calendar sessions are no longer part of this schema direction.
**Migration**: Do not add a calendar generation job, CLI, scheduler, or background workflow in this
change.
