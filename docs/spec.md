# Signapse Market Data Gateway Crypto MVP

Crypto cutover (2026-11-05): the only crypto mappings are `BTC/USDT -> BINANCE_SPOT:BTCUSDT`
and `ETH/USDT -> BINANCE_SPOT:ETHUSDT`, 24/7 UTC, price display decimals 2.
USD alternatives are retired; earlier provider experiment descriptions are historical.
See [cutover runbook](crypto-usdt-cutover.md).

Local MT5 behavior and its verified scope are recorded in the
[MT5 integration runbook](mt5-local-integration.md). Public HTTP response shapes
and the quote-only WebSocket contract remain unchanged. MT5 is disabled by
default; experimental mappings are seeded only into the dedicated local database.

HTTP integration uses the producer environment's published `/openapi.json`. The HTTP API Contract
and Error Contract sections below retain accepted behavior and target design context; they do not
prove runtime publication or replace missing generated metadata. Apply the
[OpenAPI contract rules](api-contract-rules.md) for generation, verification and handoff.
The WebSocket Stream Contract below remains the canonical reference for stream events and close codes.

- Loại tài liệu: Design
- Độc giả chính: Engineering, product, data/AI
- Source of truth cho: Behavior được chấp nhận, API/kiến trúc mục tiêu và WebSocket contract của MDG
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
| `BTC/USDT` | `CRYPTO` | `BINANCE_SPOT` | `BTCUSDT` | Supported |
| `ETH/USDT` | `CRYPTO` | `BINANCE_SPOT` | `ETHUSDT` | Supported |
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

Three additional Supported Provider mappings are available for request-wide Provider Override:
`AAPL -> YFINANCE:AAPL`, `EUR/USD -> YFINANCE:EURUSD=X`, and
`QQQ -> YFINANCE:QQQ`. `XAU/USD` is Twelve Data-only; `GC=F` and `XAUUSD=X` are not approved
alternatives. The active mapping defines the Default Provider. Each request or subscription resolves
one immutable Provider Selection, using the default when no override is supplied. Mapping existence
means verified support for quotes, all public candle timeframes, historical price, and quote
streaming; temporary provider failures do not change support or trigger automatic fallback.

MVP không hỗ trợ:

- crypto ngoài `BTC/USDT` và `ETH/USDT`
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

Client dùng canonical symbol như `BTC/USDT`. Provider adapter maps it to Binance Spot `BTCUSDT`.

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
| `4h` | `4h` | `4h` | `4h` |
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

`/health` is an upstream-independent liveness check. It does not require PostgreSQL or any market
data provider.

### Readiness

```http
GET /ready
```

Ready response:

```json
{
  "status": "READY",
  "time": "2026-06-19T10:30:00Z"
}
```

When required database configuration is absent or the PostgreSQL connectivity probe fails, the
endpoint returns `503` with the same shape and `status: "NOT_READY"`. It never calls a market-data
provider and does not expose connection strings, credentials, or exception details.

REST responses include an `X-Request-ID` header. A valid bounded inbound value is preserved; a
missing or unsafe value is replaced with a generated UUID. The identifier is not added to response
bodies.

### List supported symbols

```http
GET /v1/symbols
```

Response:

```json
{
  "symbols": [
    {
      "symbol": "BTC/USDT",
      "assetClass": "CRYPTO",
      "provider": "BINANCE_SPOT",
      "providerSymbol": "BTCUSDT",
      "enabled": true,
      "priceDisplayDecimals": 2,
      "providerMappings": [
        {"provider": "BINANCE_SPOT", "providerSymbol": "BTCUSDT", "isDefault": true}
      ]
    },
    {
      "symbol": "ETH/USDT",
      "assetClass": "CRYPTO",
      "provider": "BINANCE_SPOT",
      "providerSymbol": "ETHUSDT",
      "enabled": true,
      "priceDisplayDecimals": 2,
      "providerMappings": [
        {"provider": "BINANCE_SPOT", "providerSymbol": "ETHUSDT", "isDefault": true}
      ]
    }
  ]
}
```

`priceDisplayDecimals` is required per persisted symbol and controls public price serialization.
MDG rounds with decimal `ROUND_HALF_UP` and pads to exactly that many fractional digits for latest
quotes, historical prices, candle OHLC, and WebSocket quote prices. Provider normalization,
internal `Decimal` values, caches, persistence, and candle volume retain raw precision.

`providerMappings` lists every configured mapping for the enabled asset. The default mapping is
first, followed by remaining provider identifiers in case-sensitive ascending order. Runtime
provider health is not included in this catalog. Each mapping contains exactly `provider`,
`providerSymbol`, and `isDefault`. Enabled symbols are ordered by canonical symbol ascending;
the top-level provider fields describe the Default Provider. `priceDisplayDecimals` is an integer
from 0 through 18 inclusive.

### Get latest quotes

```http
GET /v1/quotes?symbols=BTC/USDT,ETH/USDT
```

Response:

```json
{
  "quotes": [
    {
      "symbol": "BTC/USDT",
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
- `receivedAt` is the gateway receive/snapshot timestamp. For the local MT5 feed,
  repeated REST reads preserve the original receipt time; freshness also checks
  normalized broker event time, so a replay or heartbeat cannot refresh old data.
- Asset class, provider metadata, volume, provider time, and freshness state are not exposed.
- `provider` is optional, request-wide, and case-sensitive. It selects a mapping only for assets
  that list that provider in `providerMappings`; quote requests keep HTTP `200` partial outcomes
  with per-symbol `UNSUPPORTED_PROVIDER` errors for assets without the mapping.
- Multi-symbol requests return per-symbol errors for unsupported, stale, or provider-failed symbols.
- Duplicate symbols are collapsed in first-seen order; each of the `quotes` and `errors` arrays
  preserves that request order, including when every symbol fails.
- Request-level errors are reserved for malformed input such as missing or empty `symbols`.
- Twelve Data cache misses for `EUR/USD`, `GBP/USD`, `USD/JPY`, `AUD/USD`,
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
GET /v1/candles?symbol=BTC/USDT&timeframe=1m&from=2026-06-19T00:00:00Z&to=2026-06-19T01:00:00Z
```

Response:

```json
{
  "symbol": "BTC/USDT",
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
- Closed candles are persisted and reused through PostgreSQL.
- Current forming candle may be returned with `complete = false`.
- Forming snapshots are owned by the REST candle service and are independent of WebSocket activity.
- Forming snapshots use a process-local five-second default TTL configured by
  `CANDLE_FORMING_CACHE_TTL_SECONDS`; the key includes canonical symbol, Provider Selection/provider
  symbol, and timeframe. Concurrent misses for the same key are single-flight.
- A forming snapshot is evicted at TTL expiry or when its `closeTime` is reached. It is never
  relabeled as complete in cache. If refresh after expiry fails, the response is
  `503 PROVIDER_UNAVAILABLE`; the expired snapshot is not returned and polling is not rate-limited.
- For `limit=1`, a fresh forming candle wins over a completed candle; if no eligible data exists,
  the successful response contains `candles: []`.
- Candle windows use exact UTC half-open ranges: `from` is inclusive and resolved `to` is
  exclusive. Public boundaries do not need to align to timeframe boundaries.
- `to` is optional; when omitted, the gateway captures request-time UTC once and always returns
  that resolved value in the response.
- Candle query modes are distinct:

  | Mode | Query shape | Semantics |
  | --- | --- | --- |
  | Exact range | `from + to` | Return provider-backed candles with `from <= openTime < to`. |
  | Range to request time | `from` | Exact range from `from` through one captured `requestNow`. |
  | Forward slot limit | `from + limit` | Scan the next eligible timeframe slots from `from`. |
  | Backward slot limit | `to + limit` | Scan the latest eligible timeframe slots strictly before `to`. |
  | Latest slot limit | `limit` | Scan the latest eligible timeframe slots before one captured `requestNow`. |
  | Forward actual count | `from + count` | Return up to `count` provider-backed snapshots with `openTime >= from`. |
  | Backward actual count | `to + count` | Return up to `count` provider-backed snapshots with `openTime < to`. |
  | Latest actual count | `count` | Return up to `count` provider-backed snapshots before one captured `requestNow`. |

- `limit` counts eligible timeframe slots, not actual candle rows. A provider or session gap may
  therefore make `candles.length < limit`.
- `count` counts unique Provider-backed Candle Snapshots. Its public maximum is `1000`; it may
  return fewer rows when history is exhausted, provider/session gaps remain, or the internal
  `MAX_CANDLE_COUNT_SCAN_SLOTS` budget is reached. It never creates synthetic OHLCV candles.
- Provider-backed `count` execution scans eligible opens lazily in bounded pages. The initial page
  contains no more than the requested `count` and the provider-safe page capacity; later pages are
  derived only when earlier pages did not supply enough unique rows, up to the same internal scan
  budget. A fully persisted page makes no provider request.
- MT5 backward/latest `count` scans exclude opens after captured current time, even when `to`
  is in the future; an open exactly at current time remains eligible when it is before `to`.
  The response retains the requested cutoff. Follow-up MT5 pages target the remaining row count;
  empty pages grow progressively within the page capacity and existing scan budget to cross gaps.
- When a count page is incomplete, MDG makes one logical contiguous request through the immutable
  selected Provider Mapping, even when the window crosses a closed session. The selected adapter
  may split that logical window into provider-native range-limited requests; Count Query Execution
  does not select a fallback provider or contain provider-specific range rules.
- `count` includes an eligible forming snapshot as one row with `complete = false`. If forming and
  completed snapshots share an `openTime`, the completed snapshot wins; the response is sorted by
  `openTime` ascending.
- `from + to + count` and `limit + count` are invalid and return `400 INVALID_TIME_RANGE`.
  Non-integer, zero, negative, or greater-than-1000 `count` values return the same error.
- `before` is not supported. Requests containing it return `400 INVALID_TIME_RANGE`; clients use
  `to + limit` for slot-based backward scans or `to + count` for actual-row scans.
- A valid count query with no history returns `200` with `candles: []`. Provider timeout,
  rate-limit, transport, configuration, or normalization failures remain `503 PROVIDER_UNAVAILABLE`.
- Count responses keep the existing top-level shape. Their `from`/`to` boundaries describe the
  Candle History Window actually scanned: forward scans end at the last page boundary, while
  backward/latest scans retain their exclusive cutoff and move `from` to the earliest scanned page.
  They do not add `hasMoreBefore`, `nextBefore`, cursor, or partial-result metadata.
- MDG does not impose a total request deadline or stop valid work at a hard elapsed-time threshold;
  Signapse owns its caller timeout. Individual provider operations retain finite configured
  timeouts, and caller cancellation still propagates.
- Exact ranges remain pure: MDG never expands them into earlier history. Any fallback, repeated
  count request, or merge policy for chart display belongs to the WS Java consumer.
- Gateway should reject unsupported timeframe values.
- Historical candle timeframes are `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`, and `1mo`.
- Gateway enforces `MAX_CANDLES_PER_REQUEST`.
- `provider` is optional and selects one configured mapping for the asset. Empty or repeated values
  return `400 INVALID_PROVIDER`; an unmapped value returns `400 UNSUPPORTED_PROVIDER`.
- Closed candles are read from PostgreSQL first. Exact-range and slot-based `limit` requests fetch
  only their missing contiguous sections; incomplete `count` pages use the one logical contiguous
  provider window described above.
- Missing ranges are routed through the selected Provider Mapping. When `provider` is omitted,
  the selected mapping is the asset's persisted Default Provider; an explicit override routes
  the same candle flow through that exact mapping.
- Missing `YFINANCE` candle ranges for `XAG/USD`, `BRENT`, `NATGAS`, `COFFEE`, `SUGAR`,
  `WHEAT`, `CORN`, `SPX`, `NDX`, and `DJI` are routed through yfinance `download`.
- Missing or null yfinance volume is serialized as decimal zero because the contract requires
  volume; this means upstream volume is unavailable, not measured zero trading activity.
- YFINANCE may exclude an isolated row whose only error is an inconsistent OHLC envelope when
  other eligible rows are valid. It returns the valid rows without repairing, clamping, or
  synthesizing the excluded row. An all-invalid non-empty payload, duplicate/invalid timestamp,
  missing required OHLC field, malformed/non-finite number, or negative volume fails the whole
  provider operation with sanitized `503 PROVIDER_UNAVAILABLE` and internal `INVALID_PAYLOAD`.
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
- Provider candle open times remain authoritative. Twelve Data and YFinance NYSE hourly offset
  labels such as `13:30Z` are matched on their exchange-open schedule and are not shifted onto an
  epoch-aligned grid.
- A recognized Twelve Data no-data response produces a successful empty candle list rather than
  `PROVIDER_UNAVAILABLE`.

### Get historical price

```http
GET /v1/historical-price?symbol=BTC/USDT&at=2026-06-19T10:30:12Z
```

Response:

```json
{
  "symbol": "BTC/USDT",
  "price": "104250.12",
  "pricedAt": "2026-06-19T10:30:00Z",
  "resolution": "1m"
}
```

Semantics:

- A successful response contains exactly `symbol`, `price`, `pricedAt`, and `resolution`.
- `symbol` is the canonical gateway symbol; provider identity and mapping remain internal.
- `price` is the selected completed candle close rounded with `ROUND_HALF_UP` and padded to the
  symbol's exact `priceDisplayDecimals`.
- `pricedAt` is the selected candle open timestamp, not the original requested `at`; it can be
  earlier than the finest timeframe bucket when the requested instant falls in a closed session or
  finer history is unavailable.
- `resolution` is the selected canonical historical timeframe. The gateway tries `1m`, `5m`, `1h`,
  then `1d` sequentially and stops at the first eligible completed candle. Provider-native interval
  names remain inside adapters.
- The client supplies no public `timeframe`; valid no-data, retention gaps, natural gaps, and
  closed sessions may try the next resolution, but every attempt uses the same selected provider,
  does not synthesize or resample candles, and requires `close_time <= at`.
- `provider` is optional and follows the same mapping validation as `/v1/candles`; operational
  failures return `503 PROVIDER_UNAVAILABLE` and are not hidden by coarser-resolution or
  cross-provider fallback.
- Missing, empty, invalid, or non-UTC `at` returns `400 INVALID_TIME_RANGE`.
- A future `at` is rejected with `400 INVALID_TIME_RANGE` before persistence or provider access.
- Unknown or disabled `symbol` returns `400 UNSUPPORTED_SYMBOL`.
- No eligible completed candle is available after all four resolutions are attempted at or before
  the requested instant returns `404 PRICE_NOT_FOUND`.

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
- Optional CSV filters are `types`, `currencies`, and `impact`; `limit` bounds the result count.
- `types`, `currencies`, and `impact` are trimmed, uppercased, and deduplicated CSV filters;
  an explicitly supplied filter with no non-empty values is invalid. `limit` is a single integer,
  defaults to `1000`, and accepts `1` through `5000` inclusive.
- `types` accepts `FOREX`, `METALS`, `ENERGY`, and `CRYPTO`.
- Events are ordered by `scheduledAt`, then `type`, then `key`.
- `key` is `{type}:{external_event_id}`. Database `id`, `externalEventId`, provider source, and
  upstream site fields are not exposed.
- MT5 is the active macro source, mapped to FOREX only. Other types retain readable
  legacy rows. New key is `FOREX:mt5:<occurrenceId>`; old IDs/rows are retained and
  never automatically merged across sources.
- previous retains the original previous value; revision is revised previous,
  not the native revision counter. Numbers retain native digits, K/M/B/T and percent
  suffixes. Unavailable values remain null.
- New MT5 description, newsUrl and both better/worse assessments are null. Existing
  legacy enrichment is retained; publisher source_url is not a related article URL.
- The default refresh cadence remains 300 seconds. Dedicated CalendarService RPCs
  read at most seven days each and stage the whole window before persistence.
  Native/metadata/timeout/partial errors do not persist earlier pages. No scraper
  or detail enrichment fallback remains; GET never queries the terminal.
- Empty valid ranges return `200` with `events: []`.
- Missing, invalid, non-UTC, or inverted/equal time boundaries return `400 INVALID_TIME_RANGE`.
  Invalid filters use `INVALID_TYPES`, `INVALID_CURRENCIES`, or `INVALID_IMPACT`; invalid limits
  use `INVALID_LIMIT`. Database read failures return sanitized `503 DATABASE_UNAVAILABLE`.

## WebSocket Stream Contract

### Subscribe

```text
WS /v1/stream?symbols=BTC/USDT,ETH/USDT
WS /v1/stream?symbols=AAPL,EUR/USD&provider=TWELVE_DATA
WS /v1/stream?symbols=BTC/USDT,EUR/USD,XAG/USD
```

The quote stream requires `symbols` and accepts at most one optional, case-sensitive, request-wide
`provider`. It has no `timeframe` query parameter. The gateway validates the complete symbol list,
Provider Override, registry rows, and Provider Mapping before opening an upstream subscription.
Invalid shape closes with WebSocket `1008` and a stable reason such as `INVALID_SYMBOLS`,
`TOO_MANY_SYMBOLS`, `UNSUPPORTED_SYMBOL`, `INVALID_PROVIDER`, or `UNSUPPORTED_PROVIDER`.
Registry or provider failures close with `1011` and a sanitized reason.

Any presence of `timeframe`, including `?timeframe=`, `1m`, or `1w`, is rejected before registry or
provider access with `1008 TIMEFRAME_NOT_ALLOWED`. This explicit rejection prevents candle polling
intent from being silently ignored by a quote-only connection. Candle snapshots use
`GET /v1/candles` with an explicit timeframe.

Stream interests route through each enabled symbol's persisted Provider Mapping. Twelve Data-backed
symbols use one shared process-local price stream for active interests. YFINANCE symbols use one
lazy process-local `AsyncWebSocket` and shared provider-symbol subscriptions. The gateway sends no
initial quote snapshot; clients needing an initial value use `GET /v1/quotes`.

### Quote event

```json
{
  "type": "quote",
  "symbol": "BTC/USDT",
  "price": "104250.12",
  "receivedAt": "2026-06-19T10:30:01Z"
}
```

### Status event

```json
{
  "type": "status",
  "state": "SUBSCRIBED",
  "symbols": ["BTC/USDT", "ETH/USDT"],
  "channels": ["quote"],
  "observedAt": "2026-06-19T10:30:01Z"
}
```

Status events always use `channels: ["quote"]`. `ERROR` status events additionally include stable
`code` and sanitized `message` fields. Allowed states are:

| State | Meaning |
| --- | --- |
| `CONNECTING` | Subscription accepted while the upstream quote provider is being opened. |
| `SUBSCRIBED` | At least one valid normalized quote has been received. |
| `STALE` | No valid quote has arrived within the configured freshness threshold. |
| `RECONNECTING` | The upstream quote connection is being recreated. |
| `ERROR` | The gateway cannot serve the quote stream; it closes with `1011`. |

Every valid normalized quote updates the process-local quote cache before fanout. A fresh quote
returns a stale registration to `SUBSCRIBED`; upstream reconnects emit `RECONNECTING`. The quote
stream has no candle events, candle interests, tick-to-candle aggregation, candle-session state,
or candle persistence handoff.

### Candle snapshots are REST-only

```http
GET /v1/candles?symbol=BTC/USDT&timeframe=1m&limit=1
```

The candle response shape is unchanged. `limit=1` returns the latest eligible forming candle with
`complete=false` when available, otherwise the latest completed candle, or `candles: []` when no
eligible data exists. The service works without an active WebSocket. A process-local forming
snapshot cache uses `CANDLE_FORMING_CACHE_TTL_SECONDS` (default five seconds), is isolated by
canonical symbol, Provider Selection/provider symbol, and timeframe, and uses per-key single-flight
refreshes. A snapshot is evicted at its close time or TTL expiry; an expired snapshot is never
served as complete. If refresh then fails, the endpoint returns `503 PROVIDER_UNAVAILABLE`, with no
stale forming response and no polling `429`.

WebSocket quote prices and candle HTTP OHLC values use the same `ROUND_HALF_UP`/exact-padding
policy. Candle volume remains a raw fixed-point decimal string.

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
| `INVALID_PROVIDER` | `400` | Provider Override is empty or repeated. |
| `UNSUPPORTED_PROVIDER` | `400` | Asset has no mapping for that case-sensitive Provider Identifier; quotes use per-symbol errors in HTTP `200`. |
| `UNSUPPORTED_TIMEFRAME` | `400` | Timeframe is not supported. |
| `INVALID_TIME_RANGE` | `400` | `from`/`to` is missing, invalid, or too wide. |
| `INVALID_TYPES` | `400` | Economic calendar `types` contains an unsupported value. |
| `INVALID_CURRENCIES` | `400` | Economic calendar `currencies` is malformed. |
| `INVALID_IMPACT` | `400` | Economic calendar `impact` is malformed. |
| `INVALID_LIMIT` | `400` | Economic calendar `limit` is malformed or out of range. |
| `PRICE_NOT_FOUND` | `404` | No historical price is available for the requested instant. |
| `PROVIDER_UNAVAILABLE` | `503` | Provider request or stream is unavailable, including failed forming-snapshot refresh. |
| `TIMEFRAME_NOT_ALLOWED` | WebSocket `1008` | A `timeframe` query is present on `/v1/stream`. |
| `DATA_STALE` | `503` or event status | Data is too stale for the requested operation. |
| `DATABASE_UNAVAILABLE` | `503` | A database-backed capability cannot query PostgreSQL. |
| `INTERNAL_ERROR` | `500` | Unexpected gateway failure. |

## Cache Policy

| Data | Storage | MVP policy |
| --- | --- | --- |
| Latest quote | In-memory cache | TTL 5-30 seconds |
| Forming candle snapshot | Process-local cache | REST-owned, five-second TTL, evicted at close time |
| Closed candle | PostgreSQL | Persist and reuse |
| Raw tick | Not stored | Out of scope |

MVP can start with in-memory cache because only 2 symbols are supported. Redis should be added later if gateway needs multiple replicas sharing quote state or pub/sub fanout.

## Persistence Model

MVP uses PostgreSQL for the supported-symbol registry, completed candles, and economic calendar
events. Forming candle snapshots are process-local and are not shared through PostgreSQL or Redis.

Logical model:

```text
supported_symbols
  id
  symbol
  asset_class
  price_display_decimals
  calendar_source
  calendar_name
  calendar_timezone
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

- `GET /v1/symbols` joins enabled rows from `supported_symbols` to all normalized mappings and
  derives its default fields from the single active mapping; no hard-coded runtime fallback is used.
- `symbol_provider_mappings` is the sole runtime source of provider identity.
- Multiple provider mappings can be configured for an asset, but at most one is active. Every
  enabled asset must have exactly one Default Provider. Requests may select another configured
  mapping through Provider Override; backfill uses only the default. Reads and cache/stream state
  stay isolated by Provider Selection, without aggregation or provider fallback.
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
- `symbol` stores canonical symbol such as `BTC/USDT`.
- `symbol_provider_mappings.provider_symbol` stores an upstream identifier such as `BTC/USDT`.
- Decimal values should use database decimal/numeric types, not float.

### Economic calendar persistence

`economic_calendar_events` stores the current normalized event state:

| Fields | Storage |
| --- | --- |
| `id` | Generated bigint primary key; internal only. |
| `calendar_type`, `external_event_id`, `name` | Required text. Type is constrained to `FOREX`, `METALS`, `ENERGY`, or `CRYPTO`. |
| `scheduled_at` | Required timezone-aware timestamp. |
| `currency`, `impact`, `actual`, `forecast`, `previous`, `revision`, `actual_better_worse`, `revision_better_worse` | Nullable text; upstream values such as `210K` retain their textual form. |
| `description`, `news_url` | Nullable plain-text enrichment and one absolute related news URL. |
| `enrichment_attempted_at` | Nullable timezone-aware timestamp; internal daily detail-attempt marker. |
| `first_seen_at`, `last_seen_at`, `last_changed_at`, `created_at`, `updated_at` | Required timezone-aware audit timestamps. |

Identity is unique on `(calendar_type, external_event_id)`; the same upstream ID may exist in
different types. Indexes support `scheduled_at`, `(calendar_type, scheduled_at)`, and
`(currency, scheduled_at)`. Alembic migrations and `EconomicCalendarEventModel` define the schema.

New events initialize the seen/changed timestamps. Repeated observations update `last_seen_at`
while preserving `first_seen_at`; `last_changed_at` advances only for effective normalized content
changes, including enrichment. Incoming null enrichment preserves existing values. Neither raw
provider details nor article content is persisted.

The active MT5 refresh does not claim detail enrichment. Legacy enrichment columns
and repository behavior remain available for historical rows. API reads never trigger
provider calls. See [ADR 0005](adr/0005-mt5-economic-calendar.md).

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
- Subscribe to Binance ticker streams and shared Twelve Data or yfinance price streams based on
  persisted provider mapping. Candle history remains a REST provider concern.
- Normalize provider-specific payloads into gateway DTOs.

Binance stream names should be lowercase:

```text
btcusdt@ticker
ethusdt@ticker
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
| yfinance provider dependency | yfinance 1.6.0 | Open-source Yahoo Finance wrapper used for latest quotes, historical candles, and asynchronous price streaming on planned commodities and indexes. |
| Economic calendar source | Native MQL5 CalendarService | Dedicated authenticated TCP connection, validated macro releases and persistence; no web scraping dependency. |
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
CANDLE_FORMING_CACHE_TTL_SECONDS=5
STREAM_CLIENT_QUEUE_CAPACITY=256
STREAM_PROVIDER_QUEUE_CAPACITY=1024
STREAM_IDLE_GRACE_SECONDS=5
STREAM_FRESHNESS_CHECK_SECONDS=1
ECONOMIC_CALENDAR_POLL_SECONDS=300
```

Binance public market-data endpoints do not require API keys. `TWELVEDATA_API_KEYS` is the only
Twelve Data key setting; one key or comma-separated keys are both valid. Twelve Data keys are
optional at application startup, for crypto-only requests, and for fully persisted Forex candle
reads; live Twelve Data quote or candle refreshes require at least one key.
`ECONOMIC_CALENDAR_POLL_SECONDS=0` disables the calendar listener and refresh job.
When enabled with a database, MT5_TOKEN_FILE is required. Calendar uses
MT5_CALENDAR_TCP_PORT=9002 and MT5_CALENDAR_TIMEOUT_SECONDS=60; match the MQL
Service port. Quote TCP remains on 9001.

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

- stable event name and severity
- `request_id` for REST/WebSocket work or `job_id` for standalone cron/backfill work
- job name
- provider
- calendar type
- upstream host and operation
- provider symbol
- canonical symbol
- timeframe
- request range when relevant
- public error code when relevant
- internal `failure_reason`, `retryable`, exception type, root error type/code, failure phase,
  timeout, upstream status/code, and latency when available
- retry attempt fields (`attempt`, `max_attempts`, and `retry_in_ms`) when retries are used
- calendar refresh totals (`provider_rows`, `latency_ms`) and structured job failures
- provider-backed count diagnostics also include count direction, eligible slots scanned, page and
  logical provider-call counts, persisted/provider/returned row counts, stop reason, and calendar,
  database, and provider elapsed times

Logs are JSON records written to stdout through the standard-library logging system. `LOG_LEVEL`
defaults to `INFO`. Raw provider payloads, DataFrames, API keys, DSNs, and unrestricted exception
messages are not part of the diagnostic field contract. Known operational failures omit full
tracebacks; unclassified failures may include one. High-volume queue-drop, rejected-event, and
provider-detail warnings are summarized or limited to one event key per 60 seconds and report
`suppressed_count` when applicable.

Internal failure reasons are `REQUEST_FAILED`, `TIMEOUT`, `RATE_LIMITED`, `AUTH_FAILED`,
`EMPTY_RESPONSE`, `INVALID_PAYLOAD`, `PROVIDER_NOT_CONFIGURED`, `DATABASE_QUERY_FAILED`, and
`DATABASE_WRITE_FAILED`. `retryable` describes known transient network, timeout, `429`, or `5xx`
failures; it does not itself schedule retries. Unknown or permanent failures are not retryable.
Valid no-data results remain successful; cache fallback after a provider failure is logged as
`CACHE_FALLBACK_AFTER_PROVIDER_FAILURE` without changing Provider Selection.

Partial YFINANCE OHLC quarantine emits one aggregate `WARNING` with `INVALID_PAYLOAD`,
`retryable=false`, skipped-row count, and bounded safe timestamps, scalar OHLC values, and reasons.
Equivalent warnings are rate-limited for 60 seconds; batch-fatal failures use the provider-failure
boundary. Logging configuration failure falls back to stderr and does not prevent startup.

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

- Canonical symbols remain `BTC/USDT` and `ETH/USDT`.
- Their Binance Spot provider symbols are `BTCUSDT` and `ETHUSDT`.
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


## Generated HTTP contract

All seven HTTP operations publish input metadata, success/error responses, public field aliases,
UTC timestamp formats, decimal-string schemas and X-Request-ID headers through `/openapi.json`.
Custom query parsers retain their HTTP 400 envelope; providerMappings is optional and never emitted
as null, while nullable economic-calendar fields and error.details keep their keys.
Configured quote/candle limits and cache thresholds are reflected in operation metadata.
`x-build-revision` reports SOURCE_REVISION (default unknown); local generation does not prove deployment.
