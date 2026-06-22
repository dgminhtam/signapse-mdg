## Context

The repository currently implements `/health`, the PostgreSQL-backed supported-symbol registry,
and SDK-backed latest quotes. Candle behavior exists only in `docs/spec.md` and
`docs/system-design.md`: closed candles are intended to be reusable from PostgreSQL, missing data
comes from Binance Spot klines, and a current forming candle may be returned without becoming
authoritative persistence.

The existing FastAPI patterns already separate routes, services, domain models, provider adapters,
and repositories. The official `binance-sdk-spot==9.2.0` client is synchronous, so the quote
adapter offloads calls with `asyncio.to_thread` and serializes access to its shared SDK client.
The candle implementation must preserve those boundaries and avoid leaking SDK models or
provider-specific identity into the public response.

The endpoint has one initial internal Java consumer. Its public contract should be minimal:
canonical symbol and timeframe identify the series, while asset class, provider, and provider
symbol remain gateway implementation details.

## Goals / Non-Goals

**Goals:**

- Implement a typed, provider-agnostic `GET /v1/candles` contract.
- Return exact decimal values as strings and timestamps as ISO-8601 UTC.
- Reuse persisted closed candles and fetch only missing intervals from Binance.
- Persist fetched closed candles idempotently without persisting the forming candle.
- Keep database and provider operations async-safe and bounded.
- Return the documented stable error codes instead of framework-generated validation shapes.

**Non-Goals:**

- WebSocket candle streaming or an in-memory current-candle stream cache.
- Candle retention, deletion, aggregation, or resampling.
- Cursor pagination or requests exceeding 1,000 expected candles.
- Multi-symbol candle requests, provider fallback, or cross-provider consolidation.
- Changing the `/v1/symbols` response, which remains an explicit registry/diagnostic endpoint.

## Decisions

### Publish a minimal candle response

The top-level response will contain exactly `symbol`, `timeframe`, `from`, `to`, and `candles`.
Each candle contains exactly `openTime`, `closeTime`, `open`, `high`, `low`, `close`, `volume`,
and `complete`.

`assetClass`, `provider`, and `providerSymbol` remain in internal registry, domain, persistence,
adapter, and logging contexts but are not serialized by `/v1/candles`.

Alternative: preserve the response currently illustrated in `docs/spec.md`. Rejected because it
would make a provider routing choice part of the consumer contract and conflicts with the
provider-agnostic gateway principle already applied to latest quotes.

### Use an explicit timeframe registry

The initial public values are `1m`, `5m`, `15m`, `1h`, and `1d`. A repository-owned timeframe
definition maps each public value to its duration and Binance interval string. SDK enum conversion
stays inside the Binance adapter.

Alternative: accept every Binance interval. Rejected because the gateway contract should expose
only tested values and should not inherit provider additions automatically.

### Treat requested windows as aligned half-open UTC ranges

The request interval is `[from, to)`: `from` is inclusive and `to` is exclusive. Both values must
be timezone-aware UTC timestamps aligned to the selected timeframe boundary. For fixed-duration
MVP timeframes, alignment is calculated from the Unix epoch; this makes `1d` align to midnight
UTC.

The adapter converts the exclusive boundary to Binance's inclusive millisecond `endTime` by using
`to - 1 millisecond`. Returned candles are filtered to open times inside `[from, to)`.

Alternative: accept arbitrary timestamps and silently round them. Rejected because hidden rounding
makes cache coverage, expected candle counts, and repeated requests ambiguous.

### Bound requests by both elapsed range and expected candle count

`MAX_CANDLE_RANGE_DAYS` defaults to 30 and `MAX_CANDLES_PER_REQUEST` defaults to 1,000. A request
must satisfy both limits. This prevents a nominally valid 30-day `1m` request from requiring
43,200 rows or many upstream calls.

The expected count is `(to - from) / timeframe duration`, which is exact because boundaries are
aligned. Requests exceeding either limit return `INVALID_TIME_RANGE`.

Alternative: enforce only the day range documented today. Rejected because load differs by two
orders of magnitude across supported timeframes.

### Use repository-first gap filling

The service resolves the enabled canonical symbol, reads persisted complete candles for the
requested identity and range, and identifies missing contiguous open-time slots. A full cache hit
returns without a provider call. Each missing contiguous range is fetched through Binance, then
merged by open time with persisted data.

The service does not promise synthetic continuity. Binance may return no candle for an expected
slot; the response contains the valid candles that exist after one fill attempt. The MVP does not
add a separate coverage table, so a legitimate absent slot may be checked again on a later request.

Alternative: always refetch the complete range. Rejected because it defeats PostgreSQL caching and
consumes provider quota. A coverage table was deferred because the supported pairs are liquid and
the extra migration/state model is not yet justified.

### Keep database transactions short

Candle and registry reads used by this flow will use operation-scoped async sessions. The read
session is closed before awaiting Binance. Upserts run in a separate short transaction after the
provider response has been normalized.

This requires exposing an async session-factory dependency and constructing the candle repositories
with it; existing endpoints may continue using their current request-scoped sessions.

Alternative: reuse one request-scoped `AsyncSession` across the entire service call. Rejected
because SQLAlchemy autobegin could hold a transaction and pooled connection while waiting on
external network I/O.

### Persist only complete provider candles

The adapter normalizes Binance array entries into gateway `Decimal` and UTC datetime values. At
the gateway receive time, a candle is complete when its provider close time is strictly earlier
than the receive timestamp. Complete candles are upserted by
`(provider, provider_symbol, timeframe, open_time)`; incomplete candles may be returned but are not
written.

An existing persisted complete candle wins over a provider value during the response merge.

Alternative: persist the forming candle and update it repeatedly. Rejected because REST requests
would turn transient snapshots into apparently authoritative cache records and introduce avoidable
write churn.

### Keep SDK behavior behind the existing Binance adapter boundary

The adapter calls the official SDK `klines` operation with an explicit symbol, interval, start,
end, and limit. Calls run through `asyncio.to_thread` and share the adapter's serialized SDK-client
access policy. SDK exceptions, malformed nested arrays, invalid decimals, inconsistent timestamps,
and duplicate open times become `ProviderUnavailableError`.

Cancellation continues to propagate rather than being translated into a provider error.

Alternative: call Binance directly with HTTPX. Rejected by the repository's provider integration
policy and existing SDK integration specification.

### Parse candle query parameters through a contract-aware boundary

The route will use a dedicated parser/dependency that converts the raw `symbol`, `timeframe`,
`from`, and `to` query values. Missing or malformed request values return the gateway's stable
`400` errors, rather than FastAPI's default `422` validation response.

Unsupported symbol and timeframe errors include the rejected value in sanitized `details`.
Database and provider failures remain request-level `503` responses because this endpoint serves
one series rather than a partial multi-symbol envelope.

## Risks / Trade-offs

- [A legitimate no-trade interval remains absent and is refetched later] → Accept for the liquid
  MVP symbols; add explicit range-coverage records if repeated misses become measurable.
- [Concurrent identical cache misses call Binance more than once] → Rely on idempotent database
  upserts initially; add keyed single-flight locking only if metrics show meaningful duplication.
- [Gateway and Binance clocks differ near candle close] → Base completion on the provider close
  timestamp compared with gateway receive time and never persist a candle still considered open.
- [Large sparse database ranges create several provider calls] → Cap total expected candles at
  1,000 and fetch only contiguous missing ranges.
- [A historical provider correction cannot replace a persisted candle] → Treat persisted complete
  candles as authoritative for MVP; define an explicit repair/reconciliation operation later.
- [Schema deployment precedes application deployment] → The additive table and indexes are safe
  before route activation; old application versions ignore them.

## Migration Plan

1. Add typed settings and the additive `market_data_candles` Alembic migration.
2. Deploy the application with candle domain, repository, adapter, service, route, and tests.
3. Apply `alembic upgrade head` before sending traffic to `/v1/candles`.
4. Update the Java consumer DTO to the minimal response without provider metadata.
5. Monitor provider errors, database errors, candle cache hits/misses, and request sizes.

Rollback removes or disables the route and rolls back the application. The new table may remain
unused safely; if schema rollback is required, downgrade the candle migration only after confirming
no retained candle data is needed.

## Open Questions

None.
