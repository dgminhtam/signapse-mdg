# Signapse Market Data Gateway Crypto MVP - System Design

## Request-scoped provider selection

An asset may have multiple normalized provider mappings, with exactly one default mapping. The
optional `provider` query value on quote, candle, historical-price, and stream operations is
request-wide and case-sensitive. The registry resolves one immutable Provider Selection at the
HTTP or WebSocket boundary; omitted values use the default, while an explicit value must match a
mapping for every single-asset operation or each quote symbol independently. No registry default is
mutated and no provider fallback is attempted.

Provider-aware identity is required for quote cache entries, forming candle cache entries, persisted
candle reads, and stream interests. Identity includes canonical symbol, provider, provider symbol,
and timeframe/channel where applicable. Public market-data payloads remain provider-agnostic;
`GET /v1/symbols` exposes deterministic `providerMappings` for discovery.

Historical price passes this same immutable selection through one common canonical resolution
ladder: `1m`, `5m`, `1h`, then `1d`. A coarser timeframe may be tried only for valid no-data,
retention, natural-gap, or closed-session results; selected candles must be complete at the
requested instant (`close_time <= at`), and operational provider failures remain
`PROVIDER_UNAVAILABLE`. The successful response exposes the selected `resolution` while keeping
provider-native intervals internal.

## 1. Context

Market Data Gateway is an independent service that exposes normalized market data for the supported Signapse asset universe. The crypto MVP supports only:

| Canonical symbol | Asset class | Provider | Provider symbol |
| --- | --- | --- | --- |
| `BTC/USD` | `CRYPTO` | `TWELVE_DATA` | `BTC/USD` |
| `ETH/USD` | `CRYPTO` | `BINANCE_SPOT` | `ETHUSD` |

The gateway contract is provider-agnostic for clients. Provider-specific details stay inside the registry and adapter layer.

A Twelve Data foundation now exists for the current Forex/metal catalog symbols:

| Canonical symbol | Asset class | Provider | Provider symbol |
| --- | --- | --- | --- |
| `EUR/USD` | `FOREX` | `TWELVE_DATA` | `EUR/USD` |
| `XAU/USD` | `COMMODITY` | `TWELVE_DATA` | `XAU/USD` |
| `AAPL` | `US_STOCK` | `TWELVE_DATA` | `AAPL` |
| `QQQ` | `ETF` | `TWELVE_DATA` | `QQQ` |

These rows are seeded in the registry and enabled through the provider routers.

A yfinance dependency, registry seed, latest-quote adapter, historical candle adapter, and
asynchronous stream adapter exist for planned catalog assets:

| Canonical symbol | Asset class | Provider | Provider symbol |
| --- | --- | --- | --- |
| `AUD/USD` | `FOREX` | `YFINANCE` | `AUDUSD=X` |
| `XAG/USD` | `COMMODITY` | `YFINANCE` | `SI=F` |
| `BRENT` | `COMMODITY` | `YFINANCE` | `BZ=F` |
| `NATGAS` | `COMMODITY` | `YFINANCE` | `NG=F` |
| `COFFEE` | `COMMODITY` | `YFINANCE` | `KC=F` |
| `SUGAR` | `COMMODITY` | `YFINANCE` | `SB=F` |
| `WHEAT` | `COMMODITY` | `YFINANCE` | `ZW=F` |
| `CORN` | `COMMODITY` | `YFINANCE` | `ZC=F` |
| `SPX` | `STOCK_INDEX` | `YFINANCE` | `^GSPC` |
| `NDX` | `STOCK_INDEX` | `YFINANCE` | `^NDX` |
| `DJI` | `STOCK_INDEX` | `YFINANCE` | `^DJI` |
| `GBP/USD` | `FOREX` | `YFINANCE` | `GBPUSD=X` |
| `MSFT` | `US_STOCK` | `YFINANCE` | `MSFT` |
| `NVDA` | `US_STOCK` | `YFINANCE` | `NVDA` |
| `SPY` | `ETF` | `YFINANCE` | `SPY` |
| `TSLA` | `US_STOCK` | `YFINANCE` | `TSLA` |
| `USD/JPY` | `FOREX` | `YFINANCE` | `JPY=X` |
| `WTI` | `COMMODITY` | `YFINANCE` | `CL=F` |

These `YFINANCE` rows are available through `/v1/quotes`, `/v1/candles`, and `/v1/stream`.
Commodity symbols are futures or rolling-futures proxies, including `XAG/USD -> SI=F`. Yahoo stream
event coverage is not guaranteed for every accepted symbol.

The registry contains five inactive yfinance alternatives for manual switching:
`AAPL`, `BTC-USD`, `ETH-USD`, `EURUSD=X`, and `QQQ`, owned by canonical `AAPL`, `BTC/USD`,
`ETH/USD`, `EUR/USD`, and `QQQ` respectively. `XAU/USD` has no yfinance alternative because
`GC=F` is a futures proxy rather than an approved equivalent. Selection is asset-wide and shared
by quote, candle, and stream; no route-specific selection or fallback exists.

## 2. Goals

- Serve normalized latest quotes through HTTP.
- Serve normalized historical candles through HTTP.
- Stream normalized quote and candle events through WebSocket.
- Enforce latest-quote freshness internally and expose stale HTTP data as `DATA_STALE`.
- Cache latest quotes and current candles in memory.
- Persist closed candles in PostgreSQL.
- Keep the MVP deployable as a small isolated FastAPI service.

## 3. Non-Goals

- Trading, execution, order book depth, or account APIs.
- Multi-provider aggregation or automatic fallback.
- Public authentication, multi-tenant quota, or billing.
- Raw tick storage.
- Support for crypto assets beyond `BTC/USD` and `ETH/USD`.
- Public market-data routing for FX, commodities, equities, ETFs, or indexes.

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

                              +-----------------------+
                              | Twelve Data Adapter   |
                              | Twelve Data foundation |
                              +-----------+-----------+
                                          |
                                          v
                              +-----------------------+
                              | Twelve Data REST APIs |
                              +-----------------------+
```

## 5. Component Responsibilities

### FastAPI Application

- Owns process startup, shutdown, dependency wiring, and route registration.
- Currently exposes `/health`, `/v1/symbols`, `/v1/quotes`, `/v1/candles`, and `/v1/stream`.
- Converts validation and service exceptions into stable error responses.
- Wires shared dependencies; provider streams are opened lazily when clients subscribe.

### Symbol Registry

- Defines supported canonical symbols and provider mappings.
- Validates requested symbols before any provider call.
- Defines supported timeframe mappings.
- Keeps external symbols stable if provider symbols change later.

Recommended initial registry:

```python
BTC/USD -> TWELVE_DATA:BTC/USD
ETH/USD -> TWELVE_DATA:ETH/USD
```

Recommended initial timeframes:

```python
1m -> 1m
5m -> 5m
15m -> 15m
30m -> 30m
1h -> 1h
1d -> 1d
1w -> 1w
1mo -> 1M
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

### Twelve Data Market Data Adapter

- Encapsulates the official `twelvedata==1.4.0` SDK for REST and WebSocket market data.
- Supports provider-symbol discovery/validation, latest-price normalization, and OHLC
  time-series normalization for `EUR/USD`, `GBP/USD`, `USD/JPY`, `AUD/USD`, `XAU/USD`,
  `AAPL`, `TSLA`, `NVDA`, `MSFT`, `WTI`, `SPY`, and `QQQ`.
- Supports comma-separated `TWELVEDATA_API_KEYS`, rotates REST calls across healthy process-local
  keys, and cools down key-related failures before retrying one alternate key.
- Uses one process-local Twelve Data WebSocket connection for active Forex streams and shares
  dynamic provider-symbol subscriptions across clients; the WebSocket key is selected only when
  connecting or reconnecting.
- Bridges the SDK's thread-based `on_event` callback into the asyncio runtime with
  thread-safe loop scheduling; blocking SDK connect, disconnect, subscribe, unsubscribe, and
  heartbeat calls run outside the ASGI event loop.
- Runs synchronous SDK REST calls through `asyncio.to_thread`, serializes shared SDK client
  access, and maps SDK/provider failures to the sanitized provider-unavailable boundary.
- Does not expose Twelve Data SDK request builders, payloads, or exceptions outside
  `app/providers/`.
- Is wired to public `/v1/quotes`, `/v1/candles`, and `/v1/stream` through provider routers.
- Maps the gateway's half-open candle range to Twelve Data UTC time-series boundaries.
- Normalizes missing Forex volume to zero as an unavailable-volume placeholder.
- Normalizes Twelve Data WebSocket price ticks into quote events and derives stream candles locally.

### yfinance Market Data Providers

- Locks the open-source `yfinance==1.4.1` package for latest quote, historical candle, and
  asynchronous price-stream retrieval.
- Supports the 23-symbol approved yfinance allowlist used by active defaults and inactive manual
  alternatives.
- Uses `Ticker.get_info().regularMarketPrice` behind a provider-owned adapter.
- Uses yfinance `download` for historical candles with explicit `start`, `end`, `interval`,
  `timeout`, and shared-session controls.
- Normalizes yfinance history rows into gateway candles, treating missing or null volume as
  decimal zero and preserving natural provider gaps without synthetic candles.
- Runs serialized synchronous yfinance work in `asyncio.to_thread` and applies
  `PROVIDER_HTTP_TIMEOUT_SECONDS` through the shared yfinance-compatible session.
- Uses one lazy process-local `AsyncWebSocket` for active YFINANCE stream interests, shares
  provider-symbol subscriptions across quote and candle channels, and supervises visible listener
  termination with fresh-client reconstruction and resubscription.
- Normalizes valid WebSocket price ticks into quote events and derives UTC-aligned candles with
  decimal zero volume; Yahoo day volume is ignored because it is not interval volume.
- Keeps successfully subscribed but silent symbols in `CONNECTING` without polling, remapping,
  fallback, or fabricated events.
- Keeps yfinance imports and SDK details inside `app/providers/`.
- Does not create a yfinance session, WebSocket client, network connection, or background task
  during application startup.

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
- Routes upstream interests by persisted provider mapping through a multi-provider stream router.
- Opens upstream Binance, Twelve Data, or YFINANCE streams only when at least one client is
  subscribed.
- Closes upstream streams when no matching clients remain, optionally after a short idle grace period.
- Subscribes to normalized provider events from the adapter.
- Fans out quote and candle events to matching clients.
- Emits status events such as `SUBSCRIBED`, `STALE`, `RECONNECTING`, `MARKET_CLOSED`, and `ERROR`.

## 6. Data Flow

### Latest Quote HTTP Flow

```text
Client -> GET /v1/quotes?symbols=BTC/USD,EUR/USD
  -> API validates query shape
  -> Symbol Registry validates every symbol
  -> Market Data Service checks Quote Cache
  -> If cache hit and not expired, return normalized quotes
  -> Quote Provider Router groups cache misses by persisted provider mapping
  -> Twelve Data Adapter fetches missing crypto and Forex provider symbols
  -> Adapters normalize provider payloads
  -> Service updates Quote Cache
  -> API returns normalized response
```

Quote responses include successful `quotes` and per-symbol `errors`. Missing or empty symbols
return `400 INVALID_SYMBOLS`; exceeding `MAX_QUOTE_SYMBOLS` returns
`400 TOO_MANY_SYMBOLS`. Each successful quote exposes only canonical `symbol`, decimal-string
`price`, and gateway-recorded `receivedAt`; provider and freshness metadata remain internal.
Provider failures are isolated by group.

### Price Display Formatting Flow

```text
Provider -> raw Decimal normalization
  -> domain/cache/candle aggregation/PostgreSQL retain raw Decimal
  -> Symbol Registry supplies priceDisplayDecimals
  -> HTTP/WebSocket serialization rounds ROUND_HALF_UP and pads price fields
  -> Signapse renders the returned strings directly
```

Display precision is presentation policy, not tick size or storage precision. It is not repeated
in quote, candle, historical-price, or WebSocket payloads. Latest/historical price fields and
candle OHLC use the persisted symbol precision consistently across HTTP and WebSocket; candle
volume remains a raw fixed-point decimal string.

### Candle HTTP Flow

```text
Client -> GET /v1/candles?symbol=EUR/USD&timeframe=1m&from=...[&to=...]
  -> API validates required query params
  -> If to is omitted, API captures request-time UTC once
  -> Symbol Registry validates symbol and timeframe
  -> Service validates exact UTC [from,to) and conservative candle count
  -> Service selects market-session policy from persisted asset class
  -> Service selects provider/market-aware candle schedule
  -> Repository loads persisted closed candles
  -> Service discards persisted rows outside the selected session policy
  -> Service calculates missing scheduled opens and coalesces provider ranges
  -> Candle Provider Router selects the persisted provider mapping
  -> Service fetches missing ranges from Binance, Twelve Data, or yfinance if needed
  -> Provider adapters normalize and discard known session-ineligible rows
  -> Service persists newly fetched closed candles
  -> Service merges closed candles with current forming candle if policy-eligible
  -> API returns normalized response
```

The current candle may have `complete = false`; closed candles should have `complete = true`.
The public response contains only `symbol`, `timeframe`, `from`, `to`, and `candles`; provider
identity and mapping remain internal. Response `to` is always present and contains either the
explicit request value or the exact request-time UTC instant resolved by the gateway.
Provider open timestamps remain authoritative. Binance uses the epoch-aligned schedule; verified
WTI/SPY/QQQ hourly Twelve Data rows use a minute-30 schedule, while their shorter intervals remain
epoch-aligned and daily values use date labels. Recognized Twelve Data no-data ranges and empty
yfinance history results normalize to an empty provider result instead of an operational failure.
Forex intraday candles follow the Signapse weekly quote session from Sunday 17:00 inclusive through
Friday 17:00 exclusive in `America/New_York`; `zoneinfo` and `tzdata` keep the boundary DST-aware
instead of relying on a fixed UTC offset. Forex `1d` candles use UTC weekday labels: Monday through
Friday are eligible and Saturday/Sunday are excluded. The policy intentionally does not model
holidays, early closes, late opens, exceptional closures, or provider maintenance windows. Natural
open-session provider gaps remain absent. Missing or null Twelve Data volume is represented as
decimal zero to satisfy the existing contract and does not mean measured zero activity.

### Historical Price Flow

```text
Client -> GET /v1/historical-price?symbol=...&at=...[&provider=...]
  -> API validates symbol/provider/timestamp syntax
  -> Service captures one UTC now and rejects future at
  -> Symbol Registry resolves one immutable Provider Selection
  -> Service tries 1m, 5m, 1h, then 1d sequentially
  -> Existing CandleService reads persistence/cache and fills missing ranges
  -> Provider adapter maps canonical resolution to its native interval
  -> Valid empty/no-data result advances to the next resolution
  -> Operational provider/database failure stops with a stable error
  -> Service selects only complete candles with close_time <= at
  -> API returns symbol, decimal price, pricedAt (candle open), and resolution
```

The resolver makes at most four attempts, never changes provider, never synthesizes or resamples
candles, and persists/cache-merges each candle under its actual timeframe. A successful fallback
therefore remains provider-agnostic to clients while making its coarser precision explicit.

### WebSocket Stream Flow

```text
Client -> WS /v1/stream?symbols=BTC/USD,EUR/USD&timeframe=1m
  -> API validates all symbols and timeframe
  -> Stream Manager registers client subscription
  -> Stream Manager sends CONNECTING
  -> Stream Router opens matching upstream Binance, Twelve Data, and YFINANCE streams if needed
  -> Stream Manager sends status SUBSCRIBED when upstream data is available
  -> Binance Adapter receives provider ticker/kline events
  -> Twelve Data Adapter receives Forex price ticks from one shared SDK WebSocket
  -> YFINANCE Adapter receives price ticks from one shared yfinance AsyncWebSocket
  -> Adapters normalize quote events
  -> Twelve Data and YFINANCE adapters derive candle events from price tick buckets
  -> Quote/Candle caches are updated
  -> Completed candles are queued for idempotent PostgreSQL persistence
  -> Stream Manager fans out events to matching clients
```

Twelve Data and YFINANCE stream candles are derived from price ticks for the requested timeframe.
Volume is decimal zero because those price events do not provide gateway-compatible interval
volume. The gateway does not synthesize skipped buckets; REST historical candles remain
authoritative for backfill. Silent YFINANCE interests remain `CONNECTING` until their first valid
tick.

If upstream reconnects, the stream should emit `RECONNECTING`. If open-session data exceeds the
freshness threshold, it should emit `STALE`. If a Forex candle channel is outside the weekly quote
session, it emits `MARKET_CLOSED`, is excluded from stale evaluation, and returns to `CONNECTING`
when the session reopens. The same scope limit applies as HTTP candles: holidays, early closes,
late opens, exceptional closures, and provider maintenance windows are not modeled yet.
Per-client bounded queues isolate slow consumers; an overloaded client is closed with `1013`
without blocking provider consumption or other clients.

## 7. API Surface

### HTTP

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Process health and current gateway time. |
| `GET` | `/v1/symbols` | Supported canonical symbol registry. |
| `GET` | `/v1/quotes` | Latest normalized quotes for one or more symbols. |
| `GET` | `/v1/candles` | Historical normalized candles for one symbol and timeframe. |
| `GET` | `/v1/historical-price` | Completed historical price with adaptive resolution. |

### WebSocket

| Path | Purpose |
| --- | --- |
| `/v1/stream?symbols=...&timeframe=...` | Realtime normalized quote, candle, and status events. |

## 8. Internal Models

### Symbol Definition

```text
symbol: canonical symbol, e.g. BTC/USD
asset_class: CRYPTO
provider: TWELVE_DATA
provider_symbol: provider symbol, e.g. BTC/USD
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

The normalized quote is an internal model. The public latest-quote DTO projects exactly:

```text
symbol
price: decimal string
receivedAt: UTC datetime
```

Provider identity, provider symbol, asset class, volume, provider time, and freshness state are
not exposed by `GET /v1/quotes`.

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
    price_display_decimals SMALLINT NOT NULL
        CHECK (price_display_decimals BETWEEN 0 AND 18),
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Provider identities are normalized into:

```sql
CREATE TABLE symbol_provider_mappings (
    id BIGSERIAL PRIMARY KEY,
    supported_symbol_id BIGINT NOT NULL
        REFERENCES supported_symbols(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (btrim(provider) <> ''),
    provider_symbol TEXT NOT NULL CHECK (btrim(provider_symbol) <> ''),
    is_active BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (supported_symbol_id, provider),
    UNIQUE (provider, provider_symbol)
);

CREATE UNIQUE INDEX ux_symbol_provider_mappings_active_symbol
ON symbol_provider_mappings (supported_symbol_id)
WHERE is_active;
```

Revision `20260727_0017` backfills the original provider rows, corrective revision
`20260727_0018` converts each asset's shared priority-zero mapping into its active mapping, and
revision `20260727_0019` seeds 29 mappings for 24 assets: 24 active defaults and five inactive
yfinance alternatives. Revision `20260727_0020` validates exactly one active mapping per canonical
symbol and removes the legacy provider columns from `supported_symbols`.

Runtime repositories outer-join enabled canonical symbols to their active mapping and fail closed
when one is missing. The resolved mapping is shared by quote, candle, stream, and backfill without
automatic fallback. Provider switching changes `is_active` in one transaction and requires no
legacy mirror write.

The historical seed chain first built the 24-asset catalog. Revision `0019` reconciles that catalog
to the approved matrix above while preserving unknown custom mappings and provider-owned candles.
`/v1/symbols` queries enabled rows from this table and returns
`503 DATABASE_UNAVAILABLE` when the registry cannot be queried.
`/health` remains independent of database configuration and connectivity.

Rollout order is application allowlist first, migration `0019`, then an application release that
reads active mappings while the database remains at `0019`. Apply migration `0020` only after every
runtime instance has cut over. Rollback downgrades the database first so legacy columns are
reconstructed from active mappings, then deploys the previous runtime. A provider switch starts a
new provider-owned candle history; existing candles remain under their original
`(provider, provider_symbol, timeframe, open_time)` identity and are not relabeled.

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

The candle identity remains `(provider, provider_symbol, timeframe, open_time)`.
`market_data_candles` does not reference `symbol_provider_mappings`, so historical candles remain
valid when active mappings change or are removed.

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
| `TWELVEDATA_API_KEYS` | unset | Comma-separated Twelve Data keys for process-local REST rotation and connect-time stream key selection. |
| `TWELVEDATA_REST_BASE_URL` | `https://api.twelvedata.com` | Twelve Data REST base URL. |
| `PROVIDER_WS_RECONNECT_DELAY_SECONDS` | `5` | SDK WebSocket reconnect delay. |
| `TWELVEDATA_WS_HEARTBEAT_SECONDS` | `15` | Twelve Data WebSocket heartbeat cadence while the shared Forex stream connection is active. |
| `QUOTE_STALE_AFTER_SECONDS` | `30` | Quote freshness threshold. |
| `QUOTE_CACHE_TTL_SECONDS` | `10` | Latest quote cache TTL. |
| `MAX_CANDLES_PER_REQUEST` | `1000` | Max expected timeframe slots in one candle request. |
| `MAX_QUOTE_SYMBOLS` | `10` | Max symbols in one quote request. |
| `PROVIDER_HTTP_TIMEOUT_SECONDS` | `5` | Provider REST timeout. |
| `STREAM_CLIENT_QUEUE_CAPACITY` | `256` | Per-client downstream event queue size. |
| `STREAM_PROVIDER_QUEUE_CAPACITY` | `1024` | Provider adapter ingress queue size. |
| `STREAM_PERSISTENCE_QUEUE_CAPACITY` | `256` | Completed-candle persistence queue size. |
| `STREAM_IDLE_GRACE_SECONDS` | `5` | Delay before closing unused upstream interests. |
| `STREAM_FRESHNESS_CHECK_SECONDS` | `1` | Freshness monitor interval. |

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

- Internal `received_at` is set by the gateway when it receives or creates a normalized quote.
- Internal `provider_time` is set from provider payload when available.
- A quote is stale internally when `now - received_at > QUOTE_STALE_AFTER_SECONDS`.
- Latest quote HTTP responses return per-symbol `DATA_STALE` errors when a symbol has no fresh quote.
- WebSocket streams should emit a `STALE` status when no fresh upstream event arrives within the threshold.
- Closed candles are cacheable and authoritative after persistence.
- Current candles are in-memory working state until closed.

## 13. Concurrency Model

- Use FastAPI on ASGI with async route handlers.
- Use the official Binance Spot SDK for provider REST.
- Use the official Twelve Data SDK for the multi-asset REST and WebSocket foundation.
- Keep yfinance REST and WebSocket adapters in provider-owned code, serialize REST access to shared
  session and singleton state, and supervise the asynchronous stream lifecycle independently.
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
| Provider symbol | `BTC/USD` / `ETH/USD` | Canonical symbols remain `BTC/USD` and `ETH/USD`; Twelve Data serves both required pairs. |
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

