# Signapse Market Data Gateway Crypto MVP

- Loại tài liệu: Design
- Độc giả chính: Engineering, product, data/AI
- Source of truth cho: Contract và kiến trúc mục tiêu của Market Data Gateway crypto MVP
- Không phải là: Runtime API đã triển khai, trading system, hay tài liệu chọn provider cho mọi asset class

## Mục tiêu

Market Data Gateway là một service độc lập cung cấp dữ liệu giá đã chuẩn hóa cho các asset được hỗ trợ.

MVP đầu tiên chỉ tập trung vào crypto để giảm phạm vi, giảm chi phí lấy giá, và kiểm chứng mô hình gateway trước khi mở rộng sang FX, commodity, equity, ETF, hoặc index.

Tài liệu này chỉ khóa:

- asset nào được hỗ trợ
- request input
- response output
- provider mapping
- freshness/cache semantics
- realtime event contract
- error model
- lựa chọn công nghệ cho service độc lập

Tài liệu này cố ý chỉ mô tả service contract độc lập và không mô tả cách hệ thống khác tích hợp vào gateway.

## MVP Scope

MVP chỉ hỗ trợ 2 crypto asset hiện có trong Signapse asset universe:

| Canonical symbol | Asset class | Provider | Provider symbol | Status |
| --- | --- | --- | --- | --- |
| `BTC/USD` | `CRYPTO` | `BINANCE_SPOT` | `BTCUSD` | Supported |
| `ETH/USD` | `CRYPTO` | `BINANCE_SPOT` | `ETHUSD` | Supported |

MVP không hỗ trợ:

- crypto ngoài `BTC/USD` và `ETH/USD`
- synthetic basket price hoặc consolidated global price
- exchange aggregation across nhiều sàn
- trading, order book depth, hoặc execution
- provider fallback tự động
- public client authentication
- multi-tenant quota policy

## Design Principles

### Contract first

Gateway phải được thiết kế như một service contract độc lập. Client chỉ cần biết input/output, không cần biết provider upstream là gì.

### Canonical symbol stable, provider symbol replaceable

Client dùng canonical symbol như `BTC/USD`. Provider adapter chịu trách nhiệm map sang provider symbol như `BTCUSD`.

Nếu sau này provider đổi từ Binance sang nguồn khác, contract bên ngoài không nên đổi.

### Freshness explicit

Response phải nói rõ dữ liệu có stale hay không. Dữ liệu giá realtime không nên bị trình bày như dữ liệu chắc chắn mới nếu gateway đang mất kết nối upstream.

### Decimal as string

Giá và volume trả về dưới dạng string decimal để tránh lỗi floating point giữa các runtime.

### UTC only

Timestamp trong API dùng ISO-8601 UTC.

## High-level Architecture

```text
Client
  |
  | HTTP / WebSocket
  v
Market Data Gateway
  |
  | canonical symbol registry
  | provider adapter
  | quote cache
  | candle cache
  | stream fanout
  v
Binance Spot Market Data
```

Gateway có 4 trách nhiệm chính:

1. Validate request theo supported symbol/timeframe.
2. Map canonical symbol sang provider symbol.
3. Lấy dữ liệu từ provider hoặc cache.
4. Trả output chuẩn hóa.

## Supported Timeframes

MVP nên hỗ trợ các timeframe dùng được với Binance kline:

| API timeframe | Binance interval | Notes |
| --- | --- | --- |
| `1m` | `1m` | MVP realtime default |
| `5m` | `5m` | Optional trong MVP |
| `15m` | `15m` | Optional trong MVP |
| `30m` | `30m` | Optional trong MVP |
| `1h` | `1h` | Optional trong MVP |
| `1d` | `1d` | Optional trong MVP |
| `1w` | `1w` | Optional trong MVP |
| `1mo` | `1M` | Mapping khác tên; cần test rõ |

MVP tối thiểu có thể bắt đầu với `1m`, `5m`, `15m`, `1h`, và `1d`. Các timeframe còn lại có thể được bật sau nếu contract giữ nguyên.

## HTTP API Contract

### Health

```http
GET /health
```

Response:

```json
{
  "status": "UP",
  "time": "2026-06-19T10:30:00Z"
}
```

### List supported symbols

```http
GET /v1/symbols
```

Response:

```json
{
  "symbols": [
    {
      "symbol": "BTC/USD",
      "assetClass": "CRYPTO",
      "provider": "BINANCE_SPOT",
      "providerSymbol": "BTCUSD",
      "enabled": true
    },
    {
      "symbol": "ETH/USD",
      "assetClass": "CRYPTO",
      "provider": "BINANCE_SPOT",
      "providerSymbol": "ETHUSD",
      "enabled": true
    }
  ]
}
```

### Get latest quotes

```http
GET /v1/quotes?symbols=BTC/USD,ETH/USD
```

Response:

```json
{
  "quotes": [
    {
      "symbol": "BTC/USD",
      "assetClass": "CRYPTO",
      "provider": "BINANCE_SPOT",
      "providerSymbol": "BTCUSD",
      "price": "104250.12",
      "volume": null,
      "providerTime": "2026-06-19T10:30:00Z",
      "receivedAt": "2026-06-19T10:30:01Z",
      "stale": false
    }
  ],
  "errors": []
}
```

Semantics:

- `price` is the latest trade/market price from the provider adapter.
- `volume` is `null` in the MVP.
- `providerTime` is the provider timestamp when available.
- `receivedAt` is the gateway receive/snapshot timestamp.
- `stale = true` when the quote exceeds the freshness threshold.
- Multi-symbol requests return per-symbol errors for unsupported, stale, or provider-failed symbols.
- Request-level errors are reserved for malformed input such as missing or empty `symbols`.
- The Binance MVP uses the official Spot SDK `ticker_price` operation for cache misses; the SDK
  maps this operation to Binance `/api/v3/ticker/price`.
- `providerTime` is `null` because the selected Binance response has no provider timestamp.
- Missing or empty `symbols` returns `400 INVALID_SYMBOLS`; exceeding `MAX_QUOTE_SYMBOLS`
  returns `400 TOO_MANY_SYMBOLS`.

### Get candles

```http
GET /v1/candles?symbol=BTC/USD&timeframe=1m&from=2026-06-19T00:00:00Z&to=2026-06-19T01:00:00Z
```

Response:

```json
{
  "symbol": "BTC/USD",
  "assetClass": "CRYPTO",
  "provider": "BINANCE_SPOT",
  "providerSymbol": "BTCUSD",
  "timeframe": "1m",
  "from": "2026-06-19T00:00:00Z",
  "to": "2026-06-19T01:00:00Z",
  "candles": [
    {
      "openTime": "2026-06-19T00:00:00Z",
      "closeTime": "2026-06-19T00:00:59.999Z",
      "open": "104000.00",
      "high": "104300.00",
      "low": "103900.00",
      "close": "104250.12",
      "volume": "12.345",
      "complete": true
    }
  ]
}
```

Semantics:

- Closed candles should be cacheable.
- Current forming candle may be returned with `complete = false`.
- Candle windows use UTC.
- Gateway should reject unsupported timeframe values.
- Gateway should enforce a maximum range per request to protect provider quota and database load.

## WebSocket Stream Contract

### Subscribe

```text
WS /v1/stream?symbols=BTC/USD,ETH/USD&timeframe=1m
```

On connect, gateway should validate all requested symbols and timeframe before subscribing upstream.

### Quote event

```json
{
  "type": "quote",
  "symbol": "BTC/USD",
  "assetClass": "CRYPTO",
  "provider": "BINANCE_SPOT",
  "providerSymbol": "BTCUSD",
  "price": "104250.12",
  "volume": null,
  "providerTime": "2026-06-19T10:30:00Z",
  "receivedAt": "2026-06-19T10:30:01Z",
  "stale": false
}
```

### Candle event

```json
{
  "type": "candle",
  "symbol": "BTC/USD",
  "assetClass": "CRYPTO",
  "provider": "BINANCE_SPOT",
  "providerSymbol": "BTCUSD",
  "timeframe": "1m",
  "openTime": "2026-06-19T10:30:00Z",
  "closeTime": "2026-06-19T10:30:59.999Z",
  "open": "104000.00",
  "high": "104300.00",
  "low": "103900.00",
  "close": "104250.12",
  "volume": "12.345",
  "complete": false,
  "receivedAt": "2026-06-19T10:30:01Z"
}
```

### Status event

```json
{
  "type": "status",
  "state": "SUBSCRIBED",
  "symbols": ["BTC/USD", "ETH/USD"],
  "provider": "BINANCE_SPOT",
  "observedAt": "2026-06-19T10:30:01Z"
}
```

Allowed stream states:

| State | Meaning |
| --- | --- |
| `CONNECTING` | Gateway is connecting to upstream provider. |
| `SUBSCRIBED` | Gateway is receiving data for requested symbols. |
| `STALE` | Gateway has not received fresh provider data within threshold. |
| `RECONNECTING` | Gateway is reconnecting upstream and may send stale snapshots. |
| `ERROR` | Gateway cannot serve the stream. |

## Error Contract

Errors should use a stable machine-readable code.

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

Recommended error codes:

| Code | HTTP status | Meaning |
| --- | --- | --- |
| `INVALID_SYMBOLS` | `400` | The quote symbols parameter is missing or empty. |
| `TOO_MANY_SYMBOLS` | `400` | A quote request exceeds the configured distinct-symbol limit. |
| `UNSUPPORTED_SYMBOL` | `400` | Symbol is not in the supported registry. |
| `UNSUPPORTED_TIMEFRAME` | `400` | Timeframe is not supported. |
| `INVALID_TIME_RANGE` | `400` | `from`/`to` is missing, invalid, or too wide. |
| `PROVIDER_UNAVAILABLE` | `503` | Provider request or stream is unavailable. |
| `DATA_STALE` | `503` or event status | Data is too stale for the requested operation. |
| `DATABASE_UNAVAILABLE` | `503` | A database-backed capability cannot query PostgreSQL. |
| `INTERNAL_ERROR` | `500` | Unexpected gateway failure. |

## Cache Policy

| Data | Storage | MVP policy |
| --- | --- | --- |
| Latest quote | In-memory cache | TTL 5-30 seconds |
| Current candle | In-memory cache | Updated from stream; not authoritative until closed |
| Closed candle | PostgreSQL | Persist and reuse |
| Raw tick | Not stored | Out of scope |

MVP can start with in-memory cache because only 2 symbols are supported. Redis should be added later if gateway needs multiple replicas sharing quote state or pub/sub fanout.

## Persistence Model

MVP uses PostgreSQL for the supported-symbol registry and the candle cache.

Logical model:

```text
supported_symbols
  id
  symbol
  asset_class
  provider
  provider_symbol
  enabled
  created_at
  updated_at

market_data_candles
  id
  symbol
  asset_class
  provider
  provider_symbol
  timeframe
  open_time
  close_time
  open
  high
  low
  close
  volume
  complete
  created_at
  updated_at
```

Recommended uniqueness:

```text
unique(symbol)
unique(provider, provider_symbol)
unique(provider, provider_symbol, timeframe, open_time)
```

Notes:

- `GET /v1/symbols` reads enabled rows from `supported_symbols`; no hard-coded runtime fallback is used.
- The initial migration seeds `BTC/USD -> BINANCE_SPOT:BTCUSD` and
  `ETH/USD -> BINANCE_SPOT:ETHUSD`.
- `symbol` stores canonical symbol such as `BTC/USD`.
- `provider_symbol` stores provider symbol such as `BTCUSD`.
- Decimal values should use database decimal/numeric types, not float.

## Provider Adapter

Initial provider adapter:

```text
BINANCE_SPOT
```

Responsibilities:

- Map canonical symbol to Binance symbol.
- Fetch latest quote through Binance market data endpoint.
- Fetch candles through Binance kline endpoint.
- Subscribe to Binance WebSocket streams for quote/kline events.
- Normalize provider-specific payloads into gateway DTOs.

Binance stream names should be lowercase:

```text
btcusd@ticker
ethusd@ticker
btcusd@kline_1m
ethusd@kline_1m
```

Gateway must handle Binance WebSocket reconnect and resubscribe behavior. Binance WebSocket connections are not a durable queue.

## Technology Decision

Recommended stack:

| Concern | Choice | Reason |
| --- | --- | --- |
| Language | Python 3.14.6 | Latest stable baseline for async market-data gateway and small independent service. |
| API framework | FastAPI 0.137.2 | ASGI-native, typed request/response models, OpenAPI generation. |
| Runtime server | Uvicorn 0.49.0 | Common ASGI server for FastAPI. |
| DTO validation | Pydantic 2.13.4 | Typed models, JSON serialization, validation. |
| Settings | pydantic-settings 2.14.1 | Typed environment configuration. |
| Binance provider SDK | binance-sdk-spot 9.2.0 | Official Spot REST/WebSocket foundation; synchronous REST calls are offloaded from the event loop. |
| HTTP test client | HTTPX 0.28.1 | ASGI route and integration testing only. |
| Database | PostgreSQL 18.4 | Reuse relational persistence for candle cache. |
| DB driver | asyncpg 0.31.0 | Async PostgreSQL driver. |
| ORM/migration | SQLAlchemy 2.0.51 async + Alembic 1.18.4 | Async database access and explicit migrations. |
| Cache | In-memory first | Enough for 2-symbol MVP; Redis deferred. |
| Container | Docker Compose with `python:3.14.6-slim` and `postgres:18.4` | Service should run as an isolated deployable container. |

Deferred until needed:

- Redis for shared quote cache and stream pub/sub.
- TimescaleDB for large time-series retention/query volume.
- Multi-provider routing engine.
- Provider scoring or fallback policy.
- Raw tick storage.

## Configuration

Example environment variables:

```text
APP_ENV=local
LOG_LEVEL=INFO
DATABASE_URL=postgresql+asyncpg://...
BINANCE_REST_BASE_URL=https://api.binance.com
BINANCE_WS_BASE_URL=wss://stream.binance.com:9443
PROVIDER_HTTP_TIMEOUT_SECONDS=5
QUOTE_STALE_AFTER_SECONDS=30
QUOTE_CACHE_TTL_SECONDS=10
MAX_QUOTE_SYMBOLS=10
MAX_CANDLE_RANGE_DAYS=30
```

Configuration should not hardcode secrets for MVP because Binance public market-data endpoints do not require API keys.

## Observability

Minimum useful metrics/logs:

- provider request count
- provider request latency
- provider error count
- websocket reconnect count
- active stream connection count
- quote cache hit/miss count
- candle cache hit/miss count
- stale quote count

Logs should include:

- provider
- provider symbol
- canonical symbol
- timeframe
- request range when relevant
- error code

## Security Boundary

MVP assumes gateway is private infrastructure, not a public internet product API.

Minimum controls:

- do not expose provider internals beyond documented output fields
- enforce supported symbol registry
- enforce max candle range
- enforce max symbol count per request
- reject unknown query params only if strict mode is enabled
- avoid returning stack traces in API responses

Authentication and per-client quota are out of scope for the first design. If gateway becomes public-facing or multi-consumer, auth and quota must become first-class requirements.

## Source References

- Binance Spot WebSocket Streams: <https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams>
- Binance Spot Market Data endpoints: <https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints>
- Binance Python connector SDK: <https://github.com/binance/binance-connector-python>
- FastAPI documentation: <https://fastapi.tiangolo.com/>
- HTTPX documentation (tests): <https://www.python-httpx.org/>
- SQLAlchemy asyncio documentation: <https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html>
- Alembic documentation: <https://alembic.sqlalchemy.org/>

## Resolved MVP Decisions

- Canonical symbols remain `BTC/USD` and `ETH/USD`.
- Binance provider symbols are fixed to `BTCUSD` and `ETHUSD`.
- The initial consumer is one internal Java backend service.
- The gateway remains internal-only for the MVP, but design should allow future public exposure.
- Multi-symbol quote responses return per-symbol errors instead of failing the full request.
- Quote `volume` is `null` in the MVP.
- Candle data has no automatic retention/deletion job in the MVP.
- Provider WebSocket streams are opened lazily only when clients subscribe.
- Deployment target is Docker Compose on the existing server.

## Open Questions

- Quote stale threshold should default to 10, 30, or 60 seconds?
- Is an internal provider-health endpoint needed for per-symbol operations diagnostics?

