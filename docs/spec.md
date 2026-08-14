# Signapse Market Data Gateway Crypto MVP

External integration contract: see `docs/api-contract.md` for field-level HTTP and WebSocket
schemas, required fields, types, error shapes, and close codes.

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

Registry hiện chứa các asset được hỗ trợ hoặc đã được seed để chuẩn bị provider routing:

| Canonical symbol | Asset class | Provider | Provider symbol | Status |
| --- | --- | --- | --- | --- |
| `BTC/USD` | `CRYPTO` | `TWELVE_DATA` | `BTC/USD` | Supported |
| `ETH/USD` | `CRYPTO` | `BINANCE_SPOT` | `ETHUSD` | Supported |
| `EUR/USD` | `FOREX` | `TWELVE_DATA` | `EUR/USD` | Supported |
| `GBP/USD` | `FOREX` | `YFINANCE` | `GBPUSD=X` | Supported |
| `USD/JPY` | `FOREX` | `YFINANCE` | `JPY=X` | Supported |
| `AUD/USD` | `FOREX` | `YFINANCE` | `AUDUSD=X` | Supported |
| `XAU/USD` | `COMMODITY` | `TWELVE_DATA` | `XAU/USD` | Supported |
| `AAPL` | `US_STOCK` | `TWELVE_DATA` | `AAPL` | Supported |
| `TSLA` | `US_STOCK` | `YFINANCE` | `TSLA` | Supported |
| `NVDA` | `US_STOCK` | `YFINANCE` | `NVDA` | Supported |
| `MSFT` | `US_STOCK` | `YFINANCE` | `MSFT` | Supported |
| `WTI` | `COMMODITY` | `YFINANCE` | `CL=F` | Supported |
| `SPY` | `ETF` | `YFINANCE` | `SPY` | Supported |
| `QQQ` | `ETF` | `TWELVE_DATA` | `QQQ` | Supported |
| `XAG/USD` | `COMMODITY` | `YFINANCE` | `SI=F` | Quote, candle, and stream supported |
| `BRENT` | `COMMODITY` | `YFINANCE` | `BZ=F` | Quote, candle, and stream supported |
| `NATGAS` | `COMMODITY` | `YFINANCE` | `NG=F` | Quote, candle, and stream supported |
| `COFFEE` | `COMMODITY` | `YFINANCE` | `KC=F` | Quote, candle, and stream supported |
| `SUGAR` | `COMMODITY` | `YFINANCE` | `SB=F` | Quote, candle, and stream supported |
| `WHEAT` | `COMMODITY` | `YFINANCE` | `ZW=F` | Quote, candle, and stream supported |
| `CORN` | `COMMODITY` | `YFINANCE` | `ZC=F` | Quote, candle, and stream supported |
| `SPX` | `STOCK_INDEX` | `YFINANCE` | `^GSPC` | Quote, candle, and stream supported |
| `NDX` | `STOCK_INDEX` | `YFINANCE` | `^NDX` | Quote, candle, and stream supported |
| `DJI` | `STOCK_INDEX` | `YFINANCE` | `^DJI` | Quote, candle, and stream supported |

`YFINANCE` rows use `Ticker.get_info().regularMarketPrice` for latest quotes, yfinance `download`
for historical candles, and one lazy shared `AsyncWebSocket` for stream price ticks. Yahoo may
accept a stream symbol without emitting ticks; such interests remain `CONNECTING` until usable data
arrives. Commodity mappings are futures or rolling-futures proxies; for example, `XAG/USD` maps to
`SI=F` rather than spot silver.

Five inactive mappings are available for manual provider switching:
`AAPL -> YFINANCE:AAPL`, `BTC/USD -> YFINANCE:BTC-USD`,
`ETH/USD -> YFINANCE:ETH-USD`, `EUR/USD -> YFINANCE:EURUSD=X`, and
`QQQ -> YFINANCE:QQQ`. `XAU/USD` is Twelve Data-only; `GC=F` and `XAUUSD=X` are not approved
alternatives. One asset-wide active mapping serves quote, candle, and stream, with no automatic
fallback.

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

Client dùng canonical symbol như `BTC/USD`. Provider adapter chịu trách nhiệm map sang provider symbol như `BTC/USD` hoặc `BTCUSD`.

Nếu sau này provider đổi từ Binance sang nguồn khác, contract bên ngoài không nên đổi.

### Freshness explicit

Gateway phải kiểm tra freshness trước khi trả dữ liệu. Latest quote HTTP quá cũ phải được trả
thành lỗi `DATA_STALE`; trạng thái freshness nội bộ không được expose trong successful quote.
WebSocket dùng status event riêng để báo dữ liệu stale hoặc upstream đang reconnect.

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

| API timeframe | Twelve Data | Binance | yfinance |
| --- | --- | --- | --- |
| `1m` | `1min` | `1m` | `1m` |
| `5m` | `5min` | `5m` | `5m` |
| `15m` | `15min` | `15m` | `15m` |
| `30m` | `30min` | `30m` | `30m` |
| `1h` | `1h` | `1h` | `1h` |
| `1d` | `1day` | `1d` | `1d` |
| `1w` | `1week` | `1w` | `1wk` |
| `1mo` | `1month` | `1M` | `1mo` |

Provider-native interval names stay inside adapters.

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
      "provider": "TWELVE_DATA",
      "providerSymbol": "BTC/USD",
      "enabled": true,
      "priceDisplayDecimals": 2
    },
    {
      "symbol": "ETH/USD",
      "assetClass": "CRYPTO",
      "provider": "TWELVE_DATA",
      "providerSymbol": "ETH/USD",
      "enabled": true,
      "priceDisplayDecimals": 2
    }
  ]
}
```

`priceDisplayDecimals` is required per persisted symbol and controls public price serialization.
MDG rounds with decimal `ROUND_HALF_UP` and pads to exactly that many fractional digits for latest
quotes, historical prices, candle OHLC, and WebSocket quote/candle OHLC. Provider normalization,
internal `Decimal` values, caches, candle aggregation, persistence, and candle volume retain raw
precision.

`providerMappings` lists every configured mapping for the enabled asset. The default mapping is
first, followed by remaining provider identifiers in case-sensitive ascending order. Runtime
provider health is not included in this catalog.

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
      "price": "104250.12",
      "receivedAt": "2026-06-19T10:30:01Z"
    }
  ],
  "errors": []
}
```

Semantics:

- A successful quote contains exactly `symbol`, `price`, and `receivedAt`.
- `symbol` is the canonical gateway symbol; provider identity and mapping remain internal.
- `price` is the latest trade/market price rounded with `ROUND_HALF_UP` and padded to the symbol's
  exact `priceDisplayDecimals`.
- `receivedAt` is the gateway receive/snapshot timestamp.
- Asset class, provider metadata, volume, provider time, and freshness state are not exposed.
- `provider` is optional, request-wide, and case-sensitive. It selects a mapping only for assets
  that list that provider in `providerMappings`; quote requests keep HTTP `200` partial outcomes
  with per-symbol `UNSUPPORTED_PROVIDER` errors for assets without the mapping.
- Multi-symbol requests return per-symbol errors for unsupported, stale, or provider-failed symbols.
- Request-level errors are reserved for malformed input such as missing or empty `symbols`.
- Twelve Data cache misses for `BTC/USD`, `ETH/USD`, `EUR/USD`, `GBP/USD`, `USD/JPY`, `AUD/USD`,
  `XAU/USD`, `AAPL`, `TSLA`, `NVDA`, `MSFT`, `WTI`, `SPY`, and `QQQ` are grouped by their
  persisted `TWELVE_DATA` mapping and fetched
  through the Twelve Data SDK.
- YFINANCE quote cache misses use `Ticker.get_info().regularMarketPrice` in a serialized worker
  thread. `receivedAt` is gateway receive time, not provider trade time.
- A provider-group failure affects only symbols routed to that provider; mixed requests can return
  successful crypto quotes and Forex errors, or the reverse.
- Quotes older than the configured threshold are omitted and returned as per-symbol `DATA_STALE`
  errors when refresh fails.
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

- A successful response contains exactly `symbol`, `timeframe`, `from`, `to`, and `candles`.
- Asset class, provider identity, and provider symbol remain internal to the gateway.
- Candle `open`, `high`, `low`, and `close` are rounded with `ROUND_HALF_UP` and padded to the
  symbol's exact `priceDisplayDecimals`; `volume` retains its raw fixed-point decimal string.
- Closed candles should be cacheable.
- Current forming candle may be returned with `complete = false`.
- Candle windows use exact UTC half-open ranges: `from` is inclusive and resolved `to` is
  exclusive. Public boundaries do not need to align to timeframe boundaries.
- `to` is optional; when omitted, the gateway captures request-time UTC once and always returns
  that resolved value in the response.
- Gateway should reject unsupported timeframe values.
- Historical candle timeframes are `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`, and `1mo`.
- Gateway enforces `MAX_CANDLES_PER_REQUEST`.
- `provider` is optional and selects one configured mapping for the asset. Empty or repeated values
  return `400 INVALID_PROVIDER`; an unmapped value returns `400 UNSUPPORTED_PROVIDER`.
- Closed candles are read from PostgreSQL first; only missing contiguous ranges are fetched.
- Missing ranges are routed through the selected Provider Mapping. When `provider` is omitted,
  the selected mapping is the asset's persisted Default Provider; an explicit override routes
  the same candle flow through that exact mapping.
- Missing `YFINANCE` candle ranges for `XAG/USD`, `BRENT`, `NATGAS`, `COFFEE`, `SUGAR`,
  `WHEAT`, `CORN`, `SPX`, `NDX`, and `DJI` are routed through yfinance `download`.
- Missing or null yfinance volume is serialized as decimal zero because the contract requires
  volume; this means upstream volume is unavailable, not measured zero trading activity.
- Missing or null Twelve Data Forex volume is serialized as decimal zero because the contract
  requires volume; this means upstream volume is unavailable, not measured zero trading activity.
- Forex intraday candles are filtered by the Signapse weekly quote session: Sunday 17:00 inclusive
  through Friday 17:00 exclusive in `America/New_York`. The boundary is DST-aware, so the matching
  UTC instant changes between EDT and EST.
- Forex `1d` candles use a separate pragmatic chart rule: UTC day labels Monday through Friday are
  eligible, while UTC Saturday and Sunday labels are excluded.
- Persisted rows, provider rows, and current cached candles outside the Forex session are excluded;
  closed-session slots do not count as expected gaps and are never requested or synthesized.
- Forex holidays, early closes, late opens, exceptional venue closures, and provider maintenance
  windows are out of scope for this policy.
- Natural provider gaps such as omitted open-session Forex candles remain absent and are never
  synthesized.
- Provider candle open times remain authoritative. Twelve Data offset labels such as hourly
  `13:30Z` are not shifted onto an epoch-aligned grid.
- A recognized Twelve Data no-data response produces a successful empty candle list rather than
  `PROVIDER_UNAVAILABLE`.

### Get historical price

```http
GET /v1/historical-price?symbol=BTC/USD&at=2026-06-19T10:30:12Z
```

Response:

```json
{
  "symbol": "BTC/USD",
  "price": "104250.12",
  "pricedAt": "2026-06-19T10:30:00Z"
}
```

Semantics:

- A successful response contains exactly `symbol`, `price`, and `pricedAt`.
- `symbol` is the canonical gateway symbol; provider identity and mapping remain internal.
- `price` is the selected completed candle close rounded with `ROUND_HALF_UP` and padded to the
  symbol's exact `priceDisplayDecimals`.
- `pricedAt` is the selected candle open timestamp, not the original requested `at`; it can be
  earlier than the finest timeframe bucket when the requested instant falls in a closed session or
  finer history is unavailable.
- The client supplies no public `timeframe`; the gateway uses the provider-specific historical
  resolution policy internally. Finer no-data may try a coarser timeframe, but every attempt uses
  the same selected provider and a candle must have `close_time <= at`.
- `provider` is optional and follows the same mapping validation as `/v1/candles`; operational
  failures return `503 PROVIDER_UNAVAILABLE` and are not hidden by provider fallback.
- Missing, empty, invalid, or non-UTC `at` returns `400 INVALID_TIME_RANGE`.
- Unknown or disabled `symbol` returns `400 UNSUPPORTED_SYMBOL`.
- No eligible completed candle is available in the selected provider's entire internal resolution
  policy at or before the requested instant returns `404 PRICE_NOT_FOUND`.

### Get economic calendar

```http
GET /v1/economic-calendar?from=2026-07-01T00:00:00Z&to=2026-07-08T00:00:00Z&types=FOREX,METALS
```

Response:

```json
{
  "from": "2026-07-01T00:00:00Z",
  "to": "2026-07-08T00:00:00Z",
  "events": [
    {
      "key": "FOREX:123456",
      "type": "FOREX",
      "name": "Non-Farm Employment Change",
      "currency": "USD",
      "impact": "HIGH",
      "scheduledAt": "2026-07-03T12:30:00Z",
      "actual": "210K",
      "forecast": "190K",
      "previous": "175K",
      "revision": null,
      "actualBetterWorse": "better",
      "revisionBetterWorse": null,
      "description": "Change in the number of employed people during the previous month.",
      "newsUrl": "https://www.forexfactory.com/news/123456-nfp-preview/hit",
      "firstSeenAt": "2026-07-01T00:01:00Z",
      "lastSeenAt": "2026-07-03T12:31:00Z",
      "lastChangedAt": "2026-07-03T12:31:00Z"
    }
  ]
}
```

Semantics:

- The endpoint reads persisted `economic_calendar_events` rows only; it does not scrape upstream
  calendar sites or trigger refresh jobs.
- `from` and `to` are required UTC timestamps and form a half-open range:
  `from <= scheduledAt < to`.
- Optional CSV filters are `types`, `currencies`, `impact`, and `limit`.
- `types` accepts `FOREX`, `METALS`, `ENERGY`, and `CRYPTO`.
- Events are ordered by `scheduledAt`, then `type`, then `key`.
- `key` is `{type}:{external_event_id}`. Database `id`, `externalEventId`, provider source, and
  upstream site fields are not exposed.
- `description` and `newsUrl` are nullable enrichment fields from upstream event details. `newsUrl`
  is a single related article redirect URL for downstream crawling; raw news HTML, article content,
  and history rows are not exposed.
- The refresh keeps the configured polling cadence (`300` seconds in production) for base values.
  Each run uses non-extended base scraping, preserves stored enrichment when base values are null,
  and requests details only for incomplete events not attempted during the current UTC day.
- Empty valid ranges return `200` with `events: []`.

### Crawl4AI API

This endpoint converts caller-supplied URLs to fit Markdown. It is always registered but remains
outside the public `/v1` market-data contract.

```http
POST /crawl
Content-Type: application/json

{"urls": ["https://example.com", "https://crawl4ai.com"]}
```

Response:

```json
{
  "results": [
    {"url": "https://example.com/", "content": "# Example Domain", "error": null},
    {"url": "https://crawl4ai.com/", "content": null, "error": "Crawl failed."}
  ]
}
```

Example curl:

```bash
curl --location 'http://localhost:8000/crawl' \
  --header 'Content-Type: application/json' \
  --data '{
    "urls": [
      "https://example.com",
      "https://crawl4ai.com"
    ]
  }'
```

Semantics:

- Crawl4AI is a required runtime dependency. Local development needs `uv sync` and one
  `uv run python -m playwright install chromium` setup.
- The route is always registered.
- The request accepts only `urls`, containing 1 through 10 HTTP(S) URLs; Crawl4AI configuration
  fields are rejected.
- Browser, crawl, and pruning settings are server-owned. Crawl runs use Crawl4AI's undetected
  browser adapter with stealth and magic modes, wait for the page load event, and allow two seconds
  for post-load JavaScript. Returned `content` is Crawl4AI fit Markdown without source-specific
  cleanup.
- When `CRAWL_PROXY_URL` is set, every crawl uses that server-owned HTTP, HTTPS, or SOCKS5 proxy;
  proxy configuration and credentials are never accepted by the API.
- Each result contains its normalized input `url`. Response order is unspecified; callers correlate
  results by URL rather than list position.
- URL-level failures set `content` to null and `error` to `"Crawl failed."` without discarding other
  results. Mixed success/failure and all-item failure responses use HTTP `200`.
- Browser or batch-execution failures that prevent per-URL outcomes return sanitized HTTP `502`;
  invalid request bodies return HTTP `422`.
- Each request owns one browser and submits the URL list through Crawl4AI's native batch operation,
  then closes the browser when complete.
- Do not expose this endpoint on a publicly reachable gateway. Public use requires SSRF controls
  covering DNS resolution, redirects, and browser subrequests.

## WebSocket Stream Contract

### Subscribe

```text
WS /v1/stream?symbols=BTC/USD,ETH/USD&timeframe=1m
WS /v1/stream?symbols=BTC/USD,EUR/USD&timeframe=1m
WS /v1/stream?symbols=BTC/USD,EUR/USD,XAG/USD&timeframe=1m
```

On connect, gateway should validate all requested symbols and timeframe before subscribing upstream.
Invalid subscription shape closes with WebSocket code `1008` and a stable reason such as
`INVALID_SYMBOLS`, `TOO_MANY_SYMBOLS`, `UNSUPPORTED_SYMBOL`, or `UNSUPPORTED_TIMEFRAME`.
Registry or provider failures close with `1011` and a sanitized reason.

Stream interests route through each enabled symbol's persisted provider mapping. A single optional,
case-sensitive `provider` applies to the complete subscription; if any symbol lacks that mapping,
the connection closes with `1008 UNSUPPORTED_PROVIDER` before upstream access. Empty or repeated
provider values close with `1008 INVALID_PROVIDER`. Twelve Data-backed
crypto, Forex, stock, commodity, and ETF symbols use one shared process-local Twelve Data WebSocket
price stream for all active interests. YFINANCE symbols use one lazy process-local yfinance
`AsyncWebSocket` and shared provider-symbol subscriptions.

### Quote event

```json
{
  "type": "quote",
  "symbol": "BTC/USD",
  "price": "104250.12",
  "receivedAt": "2026-06-19T10:30:01Z"
}
```

### Candle event

```json
{
  "type": "candle",
  "symbol": "BTC/USD",
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
  "channels": ["quote", "candle"],
  "observedAt": "2026-06-19T10:30:01Z"
}
```

`ERROR` status events additionally include stable `code` and sanitized `message` fields.

When a Forex candle channel is outside the Signapse weekly quote session, the stream emits
`MARKET_CLOSED` with the same status shape. The connection stays open; the candle channel is not
reported as stale and returns to `CONNECTING` when the weekly session reopens.

Allowed stream states:

| State | Meaning |
| --- | --- |
| `CONNECTING` | Gateway is connecting to upstream provider. |
| `SUBSCRIBED` | Gateway is receiving data for requested symbols. |
| `STALE` | Gateway has not received fresh provider data within threshold. |
| `RECONNECTING` | Gateway is reconnecting upstream and may send stale snapshots. |
| `MARKET_CLOSED` | Requested candle channel is outside the configured market session. |
| `ERROR` | Gateway cannot serve the stream. |

Twelve Data WebSocket events are price ticks, not upstream OHLC candles. The gateway derives
stream candles locally by bucketizing price ticks into `1m`, `5m`, `15m`, `1h`, `4h`, and `1d`
timeframes with tick price as OHLC and decimal zero volume. It does not synthesize skipped buckets;
REST historical candles remain authoritative for backfill. Forex stream candles use the same weekly
session filter as `/v1/candles`; holidays, early closes, late opens, exceptional closures, and
provider maintenance windows remain out of scope.

YFINANCE WebSocket events are also price ticks. The gateway applies the same UTC bucketing and
zero-volume derived-candle behavior. Yahoo day volume is not interval volume and is ignored.
Successful subscriptions that have not emitted a valid first tick remain `CONNECTING`; the gateway
does not poll, remap provider symbols, fabricate events, or fall back to another provider.

WebSocket quote `price` and candle `open`, `high`, `low`, and `close` use the same
`ROUND_HALF_UP`/exact-padding policy as HTTP responses. Stream candle `volume` retains raw
fixed-point precision, and no `priceDisplayDecimals` field is repeated in market-data events.

SPY and QQQ candle slots use the regular US ETF session, Monday-Friday 09:30-16:00 New York time.
WTI uses Sunday 18:00-Friday 17:00 New York time with the Monday-Thursday 17:00-18:00 maintenance
window excluded. Quote events remain independent from candle-session closure.

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
| `INVALID_TYPES` | `400` | Economic calendar `types` contains an unsupported value. |
| `INVALID_CURRENCIES` | `400` | Economic calendar `currencies` is malformed. |
| `INVALID_IMPACT` | `400` | Economic calendar `impact` is malformed. |
| `INVALID_LIMIT` | `400` | Economic calendar `limit` is malformed or out of range. |
| `PRICE_NOT_FOUND` | `404` | No historical price is available for the requested instant. |
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
  enabled
  created_at
  updated_at

symbol_provider_mappings
  id
  supported_symbol_id
  provider
  provider_symbol
  is_active
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
unique(supported_symbol_id, provider)
unique(provider, provider_symbol)
unique(supported_symbol_id) where is_active
unique(provider, provider_symbol, timeframe, open_time)
```

Notes:

- `GET /v1/symbols` joins enabled rows from `supported_symbols` to their active normalized mapping;
  no hard-coded runtime fallback is used.
- `symbol_provider_mappings` is the sole runtime source of provider identity.
- Multiple provider mappings can be configured for an asset, but at most one is active. The active
  mapping is the single provider selection shared by quote, candle, stream, and backfill; there is no
  per-route selection, aggregation, or provider fallback.
- Revision `20260727_0019` seeds 29 mappings for the 24 assets: 24 active defaults and five
  inactive yfinance alternatives. Revision `20260727_0020` validates one active mapping per asset
  and removes the duplicated provider columns from `supported_symbols`.
- A provider switch deactivates the current mapping and activates the replacement in one
  transaction; no legacy mirror write is required.
- The initial migration seeded `BTC/USD -> BINANCE_SPOT:BTCUSD` and
  `ETH/USD -> BINANCE_SPOT:ETHUSD`; a later migration moves both rows to `TWELVE_DATA`.
- Deploy the expanded 23-symbol yfinance allowlist before applying revision `0019`, then verify the
  24 active defaults and five inactive alternatives before resuming provider-selection writes.
- Switching provider starts a new provider-owned candle history. Existing candle rows retain their
  recorded provider identity and are never relabeled.
- `symbol` stores canonical symbol such as `BTC/USD`.
- `symbol_provider_mappings.provider_symbol` stores an upstream identifier such as `BTC/USD`.
- Decimal values should use database decimal/numeric types, not float.

## Provider Adapter

Initial provider adapter:

```text
BINANCE_SPOT
```

Responsibilities:

- Map canonical symbols to their persisted provider symbols.
- Fetch latest quotes through the selected Binance, Twelve Data, or yfinance adapter.
- Fetch candles through Binance klines, Twelve Data time series, or yfinance `download` based on
  registry mapping.
- Subscribe to Binance quote/kline streams and shared Twelve Data or yfinance price streams based
  on persisted provider mapping.
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
| yfinance provider dependency | yfinance 1.4.1 | Open-source Yahoo Finance wrapper used for latest quotes, historical candles, and asynchronous price streaming on planned commodities and indexes. |
| Economic calendar dependency | market-calendar-tool 0.2.2 | Scrapes ForexFactory, MetalsMine, EnergyExch, and CryptoCraft calendar rows for persistence. |
| HTTP test client | HTTPX 0.28.1 | ASGI route and integration testing only. |
| Database | PostgreSQL 18.4 | Reuse relational persistence for candle cache. |
| DB driver | asyncpg 0.31.0 | Async PostgreSQL driver. |
| ORM/migration | SQLAlchemy 2.0.51 async + Alembic 1.18.4 | Async database access and explicit migrations. |
| Cache | In-memory first | Enough for 2-symbol MVP; Redis deferred. |
| Container | Docker Compose with `python:3.14.6-slim` and `postgres:18.4` | Service should run as an isolated deployable container. |

Deferred until needed:

- Redis for shared quote cache and stream pub/sub.
- TimescaleDB for large time-series retention/query volume.
- Provider fallback and aggregation engine.
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
TWELVEDATA_API_KEYS=...
TWELVEDATA_REST_BASE_URL=https://api.twelvedata.com
PROVIDER_HTTP_TIMEOUT_SECONDS=5
PROVIDER_WS_RECONNECT_DELAY_SECONDS=5
QUOTE_STALE_AFTER_SECONDS=30
QUOTE_CACHE_TTL_SECONDS=10
MAX_QUOTE_SYMBOLS=10
MAX_CANDLES_PER_REQUEST=1000
STREAM_CLIENT_QUEUE_CAPACITY=256
STREAM_PROVIDER_QUEUE_CAPACITY=1024
STREAM_PERSISTENCE_QUEUE_CAPACITY=256
STREAM_IDLE_GRACE_SECONDS=5
STREAM_FRESHNESS_CHECK_SECONDS=1
ECONOMIC_CALENDAR_POLL_SECONDS=300
```

Binance public market-data endpoints do not require API keys. `TWELVEDATA_API_KEYS` is the only
Twelve Data key setting; one key or comma-separated keys are both valid. Twelve Data keys are
optional at application startup, for crypto-only requests, and for fully persisted Forex candle
reads; live Twelve Data quote or candle refreshes require at least one key.
`ECONOMIC_CALENDAR_POLL_SECONDS=0` disables the in-process economic calendar refresh cronjob.

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
- `BTC/USD` and `ETH/USD` provider symbols are `BTC/USD` and `ETH/USD` for Twelve Data.
- The initial consumer is one internal Java backend service.
- The gateway remains internal-only for the MVP, but design should allow future public exposure.
- Multi-symbol quote responses return per-symbol errors instead of failing the full request.
- Successful latest quotes expose only `symbol`, `price`, and `receivedAt`.
- Candle data has no automatic retention/deletion job in the MVP.
- Provider WebSocket streams are opened lazily only when clients subscribe.
- Deployment target is Docker Compose on the existing server.

## Open Questions

- Quote stale threshold should default to 10, 30, or 60 seconds?
- Is an internal provider-health endpoint needed for per-symbol operations diagnostics?

