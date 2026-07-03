## Context

The gateway has grown from one Binance adapter into Binance, Twelve Data, and yfinance REST and
WebSocket adapters. Several rules are now repeated in multiple provider modules:

- parse numeric provider payloads into finite positive or non-negative `Decimal` values
- resolve gateway timeframe duration for candle close times
- construct SDK clients from the same deployment settings
- maintain small stream-provider helper loops and aliases

The refactor is internal. Public quote, candle, stream, cache, repository, and API contracts remain
unchanged.

## Goals / Non-Goals

**Goals:**

- Remove copy-pasted provider normalization where the validation rule is identical.
- Use `app.domain.timeframes` as the single source for gateway timeframe duration.
- Keep SDK details behind `app/providers/`.
- Reduce provider builder duplication without changing FastAPI dependency override behavior.
- Keep the implementation small enough to review as mechanical refactor plus existing tests.

**Non-Goals:**

- No new provider abstraction layer.
- No new dependency.
- No API, schema, migration, cache, or route contract change.
- No rewrite of stream subscription state machines.
- No unifying provider allowlists or provider-specific interval-name maps.

## Decisions

### Shared Decimal Normalization

Create a small `app/providers/normalization.py` helper for common Decimal parsing. Provider modules
will use it only where their current rules match: reject bools, reject unsupported input types,
reject non-finite values, reject negatives, and optionally reject zero for price/OHLC fields.

Alternative considered: keep per-provider parsers. That preserves locality but keeps five copies of
the same edge-case logic.

### Timeframe Duration Source

Remove duplicated `_INTERVAL_DURATIONS` maps from REST candle providers and use
`get_timeframe(provider_interval).duration`. Provider-specific interval-name maps stay local because
Binance and Twelve Data still need provider SDK-specific interval identifiers.

Alternative considered: create a provider interval registry. That is more abstraction than this
cleanup needs.

### Provider Builder Cleanup

Extract only duplicated construction:

- one internal Binance REST client builder used by quote and candle provider builders
- one yfinance provider builder, with compatibility wrappers if that keeps route/test edits smaller

Alternative considered: create a generic provider factory. There is no common construction shape
across all SDKs, so a factory would add indirection without removing real complexity.

### Stream Cleanup

Apply only local simplifications:

- instantiate `PriceTickCandleBuilder` directly in Twelve Data stream provider
- reduce duplicated `_symbol_for_interest` lookup logic
- simplify stream route registry mapping after symbol repository lookup

The stream subscription state machines stay as-is.

## Risks / Trade-offs

- Shared Decimal helper subtly changes accepted payloads -> Mitigation: port existing parser rules
  exactly and run current provider normalization tests.
- `get_timeframe(provider_interval)` returns `None` for unsupported values -> Mitigation: keep the
  existing `ProviderUnavailableError` boundary.
- Builder cleanup may break FastAPI dependency overrides -> Mitigation: keep exported wrapper names
  when that avoids route/test churn.
- Refactor can balloon into architecture work -> Mitigation: stop after the listed duplicate code is
  removed; no new provider base classes.
