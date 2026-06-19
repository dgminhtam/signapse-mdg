# Signapse Market Data Gateway Crypto MVP - System Design

## 1. Context

Market Data Gateway is an independent service that exposes normalized market data for the supported Signapse asset universe. The crypto MVP supports only:

| Canonical symbol | Asset class | Provider | Provider symbol |
| --- | --- | --- | --- |
| `BTC/USD` | `CRYPTO` | `BINANCE_SPOT` | `BTCUSD` |
| `ETH/USD` | `CRYPTO` | `BINANCE_SPOT` | `ETHUSD` |

The gateway contract is provider-agnostic for clients. Provider-specific details stay inside the registry and adapter layer.

## 2. Goals

- Serve normalized latest quotes through HTTP.
- Serve normalized historical candles through HTTP.
- Stream normalized quote and candle events through WebSocket.
- Keep freshness explicit through `stale`, `providerTime`, and `receivedAt`.
- Cache latest quotes and current candles in memory.
- Persist closed candles in PostgreSQL.
- Keep the MVP deployable as a small isolated FastAPI service.

## 3. Non-Goals

- Trading, execution, order book depth, or account APIs.
- Multi-provider aggregation or automatic fallback.
- Public authentication, multi-tenant quota, or billing.
- Raw tick storage.
- Support for crypto assets beyond `BTC/USD` and `ETH/USD`.
- Support for FX, commodities, equities, ETFs, or indexes.

## 4. Architecture

```text
                  +-------------------------+
                  |         Clients         |
                  | HTTP / WebSocket        |
                  +-----------+-------------+
                              |
                              v
                  +-------------------------+
                  |   FastAPI Application   |
                  | routes + validation     |
                  +-----------+-------------+
                              |
        +---------------------+----------------------+
        |                     |                      |
        v                     v                      v
+---------------+     +---------------+      +----------------+
| Symbol        |     | Market Data   |      | Stream         |
| Registry      |     | Service       |      | Manager        |
+-------+-------+     +-------+-------+      +--------+-------+
        |                     |                       |
        |                     v                       v
        |             +---------------+       +----------------+
        |             | Quote/Candle  |       | WebSocket      |
        |             | Cache         |       | Fanout         |
        |             +-------+-------+       +--------+-------+
        |                     |                       |
        +---------------------+-----------+-----------+
                                          |
                                          v
                              +-----------------------+
                              | Binance Spot Adapter  |
                              | REST + WebSocket      |
                              +-----------+-----------+
                                          |
                                          v
                              +-----------------------+
                              | Binance Spot Market   |
                              | Data APIs             |
                              +-----------------------+
```

## 5. Component Responsibilities

### FastAPI Application

- Owns process startup, shutdown, dependency wiring, and route registration.
- Currently exposes `/health`, `/v1/symbols`, and `/v1/quotes`.
- Converts validation and service exceptions into stable error responses.
- Wires shared dependencies; provider streams are opened lazily when clients subscribe.

### Symbol Registry

- Defines supported canonical symbols and provider mappings.
- Validates requested symbols before any provider call.
- Defines supported timeframe mappings.
- Keeps external symbols stable if provider symbols change later.

Recommended initial registry:

```python
BTC/USD -> BINANCE_SPOT:BTCUSD
ETH/USD -> BINANCE_SPOT:ETHUSD
```

Recommended initial timeframes:

```python
1m -> 1m
5m -> 5m
15m -> 15m
1h -> 1h
1d -> 1d
```

### Market Data Service

- Orchestrates validation, cache lookup, provider calls, and persistence.
- Implements all freshness semantics.
- Returns all decimal values as strings in external DTOs.
- Returns per-symbol quote errors instead of failing an entire multi-symbol quote request.
- Enforces request limits such as max symbols per quote request and max candle range.

### Binance Spot Adapter

- Encapsulates the official `binance-sdk-spot==9.2.0` REST integration and future SDK-backed
  WebSocket details.
- Maps provider payloads into internal normalized quote and candle models.
- Runs synchronous SDK REST calls through `asyncio.to_thread`, serializes shared SDK client
  access, and owns upstream timeout and retry policy.
- Does not expose Binance-specific payloads outside the adapter boundary.

### Quote Cache

- Stores latest quote per canonical symbol in memory.
- Applies `QUOTE_CACHE_TTL_SECONDS` for HTTP quote cache reuse.
- Marks quotes stale when `receivedAt` is older than `QUOTE_STALE_AFTER_SECONDS`.
- May be replaced by Redis later without changing API DTOs.

### Candle Cache and Repository

- Stores current forming candles in memory.
- Persists closed candles in PostgreSQL.
- Reads closed candles from PostgreSQL before calling provider REST.
- Upserts closed candles by `(provider, provider_symbol, timeframe, open_time)`.

### Stream Manager

- Accepts client WebSocket subscriptions.
- Validates all symbols and timeframe before accepting a stream.
- Opens upstream Binance streams only when at least one client is subscribed.
- Closes upstream streams when no matching clients remain, optionally after a short idle grace period.
- Subscribes to normalized provider events from the adapter.
- Fans out quote and candle events to matching clients.
- Emits status events such as `SUBSCRIBED`, `STALE`, `RECONNECTING`, and `ERROR`.

## 6. Data Flow

### Latest Quote HTTP Flow

```text
Client -> GET /v1/quotes?symbols=BTC/USD,ETH/USD
  -> API validates query shape
  -> Symbol Registry validates every symbol
  -> Market Data Service checks Quote Cache
  -> If cache hit and not expired, return normalized quotes
  -> If cache miss or expired, batch missing provider symbols through
     Binance SDK ticker_price(symbols=[...])
  -> Adapter normalizes provider payload
  -> Service updates Quote Cache
  -> API returns normalized response
```

Quote responses include successful `quotes` and per-symbol `errors`. Missing or empty symbols
return `400 INVALID_SYMBOLS`; exceeding `MAX_QUOTE_SYMBOLS` returns
`400 TOO_MANY_SYMBOLS`. The Binance ticker-price payload has no timestamp, so
`providerTime` is `null` and `receivedAt` is recorded by the gateway.

### Candle HTTP Flow

```text
Client -> GET /v1/candles?symbol=BTC/USD&timeframe=1m&from=...&to=...
  -> API validates required query params
  -> Symbol Registry validates symbol and timeframe
  -> Service validates UTC range and max range
  -> Repository loads persisted closed candles
  -> Service fetches missing range from Binance Adapter if needed
  -> Service persists newly fetched closed candles
  -> Service merges closed candles with current forming candle if applicable
  -> API returns normalized response
```

The current candle may have `complete = false`; closed candles should have `complete = true`.

### WebSocket Stream Flow

```text
Client -> WS /v1/stream?symbols=BTC/USD,ETH/USD&timeframe=1m
  -> API validates all symbols and timeframe
  -> Stream Manager registers client subscription
  -> Stream Manager opens the matching upstream Binance stream if needed
  -> Stream Manager sends status SUBSCRIBED when upstream data is available
  -> Binance Adapter receives provider ticker/kline events
  -> Adapter normalizes events
  -> Quote/Candle caches are updated
  -> Stream Manager fans out events to matching clients
```

If upstream reconnects, the stream should emit `RECONNECTING`. If data exceeds the freshness threshold, it should emit `STALE`.

## 7. API Surface

### HTTP

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Process health and current gateway time. |
| `GET` | `/v1/symbols` | Supported canonical symbol registry. |
| `GET` | `/v1/quotes` | Latest normalized quotes for one or more symbols. |
| `GET` | `/v1/candles` | Planned; not implemented in the current scope. |

### WebSocket

| Path | Purpose |
| --- | --- |
| `/v1/stream?symbols=...&timeframe=...` | Planned; not implemented in the current scope. |

## 8. Internal Models

### Symbol Definition

```text
symbol: canonical symbol, e.g. BTC/USD
asset_class: CRYPTO
provider: BINANCE_SPOT
provider_symbol: provider symbol, e.g. BTCUSD
enabled: boolean
```

### Normalized Quote

```text
symbol
asset_class
provider
provider_symbol
price: Decimal
volume: Decimal | null
provider_time: datetime | null
received_at: datetime
stale: boolean
```

External DTOs serialize `price` as a decimal string. Quote `volume` is `null` for the MVP.

### Normalized Candle

```text
symbol
asset_class
provider
provider_symbol
timeframe
open_time
close_time
open: Decimal
high: Decimal
low: Decimal
close: Decimal
volume: Decimal
complete: boolean
received_at: datetime | null
```

External DTOs serialize OHLCV fields as decimal strings.

## 9. Persistence Design

Initial symbol registry table:

```sql
CREATE TABLE supported_symbols (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL UNIQUE,
    asset_class TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_symbol TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_symbol)
);
```

The initial Alembic migration seeds `BTC/USD -> BINANCE_SPOT:BTCUSD` and
`ETH/USD -> BINANCE_SPOT:ETHUSD`. `/v1/symbols` queries enabled rows from this
table and returns `503 DATABASE_UNAVAILABLE` when the registry cannot be queried.
`/health` remains independent of database configuration and connectivity.

Initial candle table:

```sql
CREATE TABLE market_data_candles (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time TIMESTAMPTZ NOT NULL,
    close_time TIMESTAMPTZ NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume NUMERIC NOT NULL,
    complete BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_symbol, timeframe, open_time)
);
```

Recommended indexes:

```sql
CREATE INDEX ix_market_data_candles_symbol_timeframe_open_time
ON market_data_candles (symbol, timeframe, open_time);

CREATE INDEX ix_market_data_candles_provider_symbol_timeframe_open_time
ON market_data_candles (provider, provider_symbol, timeframe, open_time);
```

## 10. Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `local` | Runtime environment. |
| `LOG_LEVEL` | `INFO` | Application log level. |
| `DATABASE_URL` | unset | Async PostgreSQL connection string; required by migrations and database-backed endpoints. |
| `DATABASE_POOL_SIZE` | `5` | Base async connection pool size. |
| `DATABASE_POOL_MAX_OVERFLOW` | `5` | Additional connections allowed above the pool size. |
| `DATABASE_POOL_TIMEOUT_SECONDS` | `5` | Maximum wait for a pooled connection. |
| `BINANCE_REST_BASE_URL` | `https://api.binance.com` | Binance REST base URL. |
| `BINANCE_WS_BASE_URL` | `wss://stream.binance.com:9443` | Binance WebSocket base URL. |
| `QUOTE_STALE_AFTER_SECONDS` | `30` | Quote freshness threshold. |
| `QUOTE_CACHE_TTL_SECONDS` | `10` | Latest quote cache TTL. |
| `MAX_CANDLE_RANGE_DAYS` | `30` | Max candle query range. |
| `MAX_QUOTE_SYMBOLS` | `10` | Max symbols in one quote request. |
| `PROVIDER_HTTP_TIMEOUT_SECONDS` | `5` | Provider REST timeout. |

## 11. Error Handling

All API errors should use this response shape:

```json
{
  "error": {
    "code": "UNSUPPORTED_SYMBOL",
    "message": "Symbol is not supported by this gateway.",
    "details": {
      "symbol": "SOL/USD"
    }
  }
}
```

Multi-symbol quote responses use a per-symbol error list:

```json
{
  "quotes": [],
  "errors": [
    {
      "symbol": "SOL/USD",
      "code": "UNSUPPORTED_SYMBOL",
      "message": "Symbol is not supported by this gateway."
    }
  ]
}
```

| Code | HTTP status | Trigger |
| --- | --- | --- |
| `INVALID_SYMBOLS` | `400` | Missing or empty quote symbols parameter. |
| `TOO_MANY_SYMBOLS` | `400` | Too many distinct symbols in a quote request. |
| `UNSUPPORTED_SYMBOL` | `400` | Unknown or disabled canonical symbol. |
| `UNSUPPORTED_TIMEFRAME` | `400` | Unknown timeframe. |
| `INVALID_TIME_RANGE` | `400` | Missing, invalid, inverted, or too-wide time range. |
| `PROVIDER_UNAVAILABLE` | `503` | REST or stream provider failure. |
| `DATA_STALE` | `503` | Operation requires fresh data but only stale data exists. |
| `INTERNAL_ERROR` | `500` | Unexpected server failure. |

## 12. Freshness and Cache Rules

- `receivedAt` is set by the gateway when it receives or creates the normalized data point.
- `providerTime` is set from provider payload when available.
- `stale = true` when `now - receivedAt > QUOTE_STALE_AFTER_SECONDS`.
- Latest quote HTTP responses return per-symbol `DATA_STALE` errors when a symbol has no fresh quote.
- WebSocket streams should emit a `STALE` status when no fresh upstream event arrives within the threshold.
- Closed candles are cacheable and authoritative after persistence.
- Current candles are in-memory working state until closed.

## 13. Concurrency Model

- Use FastAPI on ASGI with async route handlers.
- Use the official Binance Spot SDK for provider REST.
- Offload synchronous SDK REST operations with `asyncio.to_thread` and serialize shared SDK
  client access.
- Use SQLAlchemy 2 async sessions for PostgreSQL access.
- Run provider WebSocket consumers as background asyncio tasks created on demand by subscriptions.
- Protect in-memory quote and current-candle caches with an `asyncio.Lock` or a small cache abstraction that owns mutation.
- Keep fanout non-blocking: one slow client should not block provider consumption or other clients.

## 14. Observability

Minimum metrics:

- Provider REST request count, latency, and error count.
- Provider WebSocket reconnect count.
- Active downstream WebSocket connection count.
- Quote cache hit and miss count.
- Candle cache hit and miss count.
- Stale quote count.

Structured log fields:

- `provider`
- `provider_symbol`
- `symbol`
- `timeframe`
- `from`
- `to`
- `error_code`
- `request_id`

## 15. Security Boundary

The MVP assumes private infrastructure and one initial Java backend consumer.

Minimum controls:

- Enforce supported symbol registry.
- Enforce max symbols per quote request.
- Enforce max candle range.
- Avoid returning stack traces.
- Do not expose provider payloads beyond documented normalized fields.
- Keep provider base URLs configurable but controlled by deployment.

Authentication and per-client quotas should be added before exposing the service outside trusted infrastructure.

Keep extension points for future public exposure: auth middleware, rate limits, CORS policy, API keys, and public-safe metrics boundaries.

## 16. Suggested Project Layout

```text
app/
  main.py
  api/
    routes_health.py
    routes_symbols.py
    routes_quotes.py
    routes_candles.py
    routes_stream.py
    errors.py
  core/
    config.py
    logging.py
    time.py
  domain/
    symbols.py
    timeframes.py
    models.py
    errors.py
  services/
    market_data.py
    freshness.py
    stream_manager.py
  providers/
    base.py
    binance_spot.py
  cache/
    quote_cache.py
    candle_cache.py
  db/
    session.py
    models.py
    repositories.py
alembic/
tests/
  unit/
  integration/
```

## 17. Implementation Plan

1. Scaffold FastAPI app, config, structured errors, and `/health`.
2. Add symbol/timeframe registry and `/v1/symbols`.
3. Add Pydantic DTOs for quote, candle, stream events, and error responses.
4. Implement Binance REST adapter for latest quote and klines.
5. Implement in-memory quote cache and `/v1/quotes`.
6. Add SQLAlchemy async models, Alembic migration, and candle repository.
7. Implement `/v1/candles` with repository-first lookup and provider fill.
8. Implement Binance WebSocket adapter and normalized event stream.
9. Add stream manager and `/v1/stream`.
10. Add tests for validation, DTO serialization, provider normalization, cache freshness, and route behavior.
11. Add Dockerfile, Docker Compose file, environment examples, and basic runbook.

## 18. Testing Strategy

Unit tests:

- Registry validation.
- Timeframe mapping.
- Decimal string serialization.
- Freshness calculation.
- Error mapping.
- Binance payload normalization.

Integration tests:

- HTTP route validation and response shape.
- Candle repository upsert and query behavior.
- Provider adapter behavior with mocked HTTP/WebSocket payloads.
- WebSocket subscription validation and fanout.

Contract tests:

- Error response shape remains stable.
- Supported symbol response remains stable.
- Quote and candle DTO fields match `docs/spec.md`.

## 19. MVP Decisions

| Decision | Default for MVP | Notes |
| --- | --- | --- |
| Provider symbol | `BTCUSD` / `ETHUSD` | Canonical symbols remain `BTC/USD` and `ETH/USD`; Binance Spot supports both required pairs. |
| Stale threshold | 30 seconds | Make configurable through `QUOTE_STALE_AFTER_SECONDS`. |
| Candle retention | No automatic deletion | Add retention only once product requirement is known. |
| Partial quote response | Per-symbol errors | Return successful quotes and symbol-level errors in the same response. |
| Quote volume | `null` | Defer trade quantity or 24h volume semantics. |
| Upstream WebSocket | Lazy by subscription | Open provider streams only when downstream clients exist. |
| Deployment | Docker Compose | Target the existing server environment. |
| Provider health endpoint | Defer | Add `/internal/provider-health` if operations need per-symbol diagnostics. |

## 20. Key Risks

- In-memory cache does not work across multiple replicas.
- Provider WebSocket streams are not durable, so reconnect gaps may require REST backfill.
- Public exposure later will require auth, quota, rate limits, and stronger abuse controls.
- Candle backfill logic must avoid duplicate writes and incomplete candle persistence mistakes.

