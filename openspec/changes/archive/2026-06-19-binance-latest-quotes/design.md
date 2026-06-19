## Context

The service already has an async FastAPI application and a PostgreSQL-backed registry containing
enabled canonical-to-provider mappings. It does not yet have a provider adapter, quote domain
model, cache, or market-data route. The first consumer is an internal Java backend, but the
contract must remain provider-agnostic and suitable for later external exposure.

Binance Spot supports the required `BTCUSD` and `ETHUSD` pairs. Its public
`GET /api/v3/ticker/price` endpoint accepts multiple symbols and returns a latest price without a
provider timestamp. The implementation must therefore distinguish provider data from the
gateway's observation time.

## Goals / Non-Goals

**Goals:**

- Serve normalized latest quotes for enabled `BTC/USD` and `ETH/USD` mappings.
- Preserve partial success for valid multi-symbol requests.
- Keep Binance payloads behind a provider protocol.
- Limit upstream traffic with a process-local cache and one batch call per refresh.
- Keep configuration, error output, and async resource lifecycle production-ready.

**Non-Goals:**

- Candles, WebSocket streams, quote persistence, Redis, or multiple replicas sharing state.
- Authentication, public quotas, provider fallback, or automatic retries.
- Additional symbols or Binance account/trading APIs.

## Decisions

### Use the database registry for request validation and mapping

The quote service loads enabled symbols from the existing repository, matches requested canonical
symbols, and uses the persisted provider symbols for Binance calls. It does not maintain a second
hard-coded mapping. This preserves the registry as the source of truth and makes disabled symbols
immediately unavailable.

Alternative considered: hard-code the two MVP mappings in the adapter. Rejected because it would
allow `/v1/symbols` and `/v1/quotes` to disagree.

### Use Binance's batch symbol-price endpoint

The adapter sends one `GET /api/v3/ticker/price` request with the JSON-encoded `symbols` query
parameter for all cache misses. It validates that every returned provider symbol was requested,
that symbols are unique, and that each price is a valid finite positive `Decimal`.

Alternative considered: call the single-symbol endpoint concurrently. Rejected because batching
uses less request weight and gives simpler partial-response accounting. The 5-minute average-price
endpoint was rejected because it does not represent the latest market price.

### Model provider time as unavailable

`providerTime` is `null` because the selected Binance payload has no event timestamp. A single UTC
`receivedAt` is captured after the complete batch response is received and successfully decoded.
`volume` remains `null`. Prices are domain `Decimal` values and API decimal strings, never floats.

### Return per-symbol outcomes in request order

The API parses a comma-separated `symbols` parameter, trims surrounding whitespace, removes
duplicates while retaining first occurrence order, and enforces `MAX_QUOTE_SYMBOLS`. Missing,
empty, or over-limit input is a request-level `400`. For otherwise valid input, the response is
`200` with ordered `quotes` and `errors`; unknown, disabled, missing-provider-response, and
provider-failed symbols do not fail successful siblings.

A registry configuration or connectivity failure remains request-level
`503 DATABASE_UNAVAILABLE`, because no requested symbol can be authoritatively validated.

### Use TTL refresh with fresh-cache fallback

The cache is keyed by canonical symbol and owns mutation behind an `asyncio.Lock`. Entries younger
than `QUOTE_CACHE_TTL_SECONDS` are normal cache hits. Older entries trigger refresh. If refresh
fails, an entry whose age does not exceed `QUOTE_STALE_AFTER_SECONDS` is returned as a fresh
fallback; an older entry yields `DATA_STALE`. A symbol with no usable entry yields
`PROVIDER_UNAVAILABLE`.

The service coalesces concurrent refresh work so simultaneous requests do not create duplicate
Binance calls for the same uncached symbols. Cache state is process-local and is lost on restart.

### Share one lifecycle-managed HTTPX client

HTTPX becomes a runtime dependency. FastAPI lifespan creates one configured `AsyncClient` and
closes it at shutdown. The adapter receives the client and configurable base URL/timeout through
dependency injection. The request path makes one attempt and maps timeout, transport, non-success
status, and invalid payload failures to sanitized provider errors.

Automatic retries are deferred: they can amplify Binance load and tail latency, and a fresh cache
already provides a bounded fallback.

## Risks / Trade-offs

- [Binance batch request fails for both pairs] -> Return fresh cached entries where possible and
  isolated provider errors for the remainder.
- [Provider payload omits or corrupts one symbol] -> Accept valid siblings and report only the
  affected symbol as unavailable.
- [In-memory cache differs across replicas] -> Keep the API contract cache-agnostic and defer Redis
  until multiple replicas are required.
- [Database lookup occurs on every request] -> Accept the small MVP cost to preserve immediate
  registry consistency; optimize only with measured evidence.
- [No provider timestamp] -> Return `providerTime=null` and document `receivedAt` as gateway time.
- [Concurrent refresh complexity] -> Keep synchronization inside the cache/service boundary and
  cover coalescing and cancellation with focused async tests.

## Migration Plan

1. Move HTTPX to locked runtime dependencies and add non-secret quote settings to `.env.example`.
2. Deploy the code with the existing supported-symbol migration already applied.
3. Smoke-test `/health`, `/v1/symbols`, and `/v1/quotes` against Binance public REST.
4. Roll back by deploying the previous application image; no database migration or data rollback
   is required.

## Open Questions

None for this change. Authentication, shared cache, retries, metrics backend, and additional
market-data endpoints remain separate future changes.
