# External API and WebSocket Contract

This document is the integration contract for external clients of the Signapse Market Data
Gateway. It describes public HTTP and WebSocket shapes only. Provider payloads, SDK models,
provider routing, and provider errors are internal implementation details unless explicitly listed
here.

## Conventions

| Rule | Contract |
| --- | --- |
| Base path | HTTP and WebSocket market-data endpoints are versioned under `/v1`. |
| Encoding | URL-encode symbols containing `/`, for example `BTC%2FUSD`. |
| Field names | JSON fields use camelCase. |
| Timestamps | ISO-8601 UTC strings ending in `Z`, for example `2026-06-22T02:59:19.184926Z`. |
| Decimal values | Base-10 strings, not JSON numbers. Clients must not parse prices as floating point when precision matters. |
| Unknown fields | Clients should ignore unknown response fields for forward compatibility. |

## Supported Values

`GET /v1/symbols` is the runtime source of truth for enabled symbols. The current seeded registry
contains these public symbols:

| Symbol | Asset class |
| --- | --- |
| `BTC/USD` | `CRYPTO` |
| `ETH/USD` | `CRYPTO` |
| `EUR/USD` | `FOREX` |
| `GBP/USD` | `FOREX` |
| `USD/JPY` | `FOREX` |
| `AUD/USD` | `FOREX` |
| `XAU/USD` | `COMMODITY` |
| `AAPL` | `US_STOCK` |
| `TSLA` | `US_STOCK` |
| `NVDA` | `US_STOCK` |
| `MSFT` | `US_STOCK` |

Supported timeframe values are `1m`, `5m`, `15m`, `1h`, and `1d`.

## Health

```http
GET /health
```

### Response `200`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `status` | string enum | yes | Current process health. Currently `UP`. |
| `time` | UTC datetime string | yes | Gateway time when the response is generated. |

```json
{
  "status": "UP",
  "time": "2026-06-22T02:59:19.184926Z"
}
```

## Supported Symbols

```http
GET /v1/symbols
```

### Response `200`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `symbols` | array of Symbol | yes | Enabled symbol registry rows in service order. May be empty. |

Symbol object:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `symbol` | string | yes | Canonical symbol clients must use in all other endpoints. |
| `assetClass` | string enum | yes | Current values: `CRYPTO`, `FOREX`, `COMMODITY`, `US_STOCK`. |
| `provider` | string | yes | Current provider mapping. This is diagnostic registry data and should not drive client business logic. |
| `providerSymbol` | string | yes | Current provider symbol mapping. This is diagnostic registry data and may change without changing `symbol`. |
| `enabled` | boolean | yes | Whether the symbol is enabled for gateway use. This endpoint returns enabled rows. |

```json
{
  "symbols": [
    {
      "symbol": "BTC/USD",
      "assetClass": "CRYPTO",
      "provider": "BINANCE_SPOT",
      "providerSymbol": "BTCUSD",
      "enabled": true
    }
  ]
}
```

## Latest Quotes

```http
GET /v1/quotes?symbols=BTC%2FUSD,ETH%2FUSD
```

### Query Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `symbols` | comma-separated string | yes | One or more canonical symbols. Whitespace is trimmed. Duplicate symbols are de-duplicated while preserving first occurrence order. |

Limits:

- At least one non-empty symbol is required.
- Maximum distinct symbols is configured by `MAX_QUOTE_SYMBOLS`; default is `10`.

### Response `200`

The endpoint returns `200` for a syntactically valid quote request, even when some or all symbols
fail. Symbol-level failures are reported in `errors`.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `quotes` | array of Quote | yes | Successful quotes, ordered by requested symbol order. |
| `errors` | array of QuoteError | yes | Per-symbol failures, ordered by requested symbol order. |

Quote object:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `symbol` | string | yes | Canonical symbol, for example `BTC/USD`. |
| `price` | decimal string | yes | Latest normalized price. |
| `receivedAt` | UTC datetime string | yes | Time the gateway received or created the normalized quote snapshot. |

QuoteError object:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `symbol` | string | yes | Requested symbol that failed. |
| `code` | string enum | yes | Stable machine-readable code. |
| `message` | string | yes | Sanitized human-readable message. |

Per-symbol quote error codes:

| Code | Meaning |
| --- | --- |
| `UNSUPPORTED_SYMBOL` | Symbol is not in the enabled registry. |
| `PROVIDER_UNAVAILABLE` | Provider refresh failed and no usable cached quote exists. |
| `DATA_STALE` | Only stale cached data exists after refresh failed. |

```json
{
  "quotes": [
    {
      "symbol": "BTC/USD",
      "price": "64196.19000000",
      "receivedAt": "2026-06-22T02:59:19.184926Z"
    }
  ],
  "errors": [
    {
      "symbol": "SOL/USD",
      "code": "UNSUPPORTED_SYMBOL",
      "message": "Symbol is not supported by this gateway."
    }
  ]
}
```

## Historical Candles

```http
GET /v1/candles?symbol=BTC%2FUSD&timeframe=1m&from=2026-06-22T00%3A00%3A00Z&to=2026-06-22T00%3A05%3A00Z
```

### Query Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `symbol` | string | yes | One canonical symbol. |
| `timeframe` | string enum | yes | One of `1m`, `5m`, `15m`, `1h`, `1d`. |
| `from` | UTC datetime string | yes | Inclusive range start. Must align to the selected timeframe. |
| `to` | UTC datetime string | yes | Exclusive range end. Must align to the selected timeframe and be greater than `from`. |

Limits:

- Range is half-open: `[from, to)`.
- Maximum range is configured by `MAX_CANDLE_RANGE_DAYS`; default is `30`.
- Maximum expected candles is configured by `MAX_CANDLES_PER_REQUEST`; default and maximum is `1000`.

### Response `200`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `symbol` | string | yes | Canonical symbol requested. |
| `timeframe` | string enum | yes | Requested timeframe. |
| `from` | UTC datetime string | yes | Inclusive response range start. |
| `to` | UTC datetime string | yes | Exclusive response range end. |
| `candles` | array of Candle | yes | Candles ordered by `openTime`. May be empty when no eligible data exists. |

Candle object:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `openTime` | UTC datetime string | yes | Candle bucket start, inclusive. |
| `closeTime` | UTC datetime string | yes | Candle bucket end timestamp. |
| `open` | decimal string | yes | Opening price for the bucket. |
| `high` | decimal string | yes | Highest price for the bucket. |
| `low` | decimal string | yes | Lowest price for the bucket. |
| `close` | decimal string | yes | Closing or latest price for the bucket. |
| `volume` | decimal string | yes | Provider volume when available. For Twelve Data symbols, `0` can mean upstream volume is unavailable. |
| `complete` | boolean | yes | `true` for closed candles, `false` for the current forming candle. |

```json
{
  "symbol": "BTC/USD",
  "timeframe": "1m",
  "from": "2026-06-22T00:00:00Z",
  "to": "2026-06-22T00:05:00Z",
  "candles": [
    {
      "openTime": "2026-06-22T00:00:00Z",
      "closeTime": "2026-06-22T00:00:59.999000Z",
      "open": "64100.00",
      "high": "64200.00",
      "low": "64090.00",
      "close": "64196.19",
      "volume": "12.345",
      "complete": true
    }
  ]
}
```

Forex intraday candles follow the Signapse weekly quote session: Sunday 17:00 inclusive through
Friday 17:00 exclusive in `America/New_York`. Forex `1d` candles include UTC weekday labels Monday
through Friday and exclude UTC Saturday/Sunday labels. Holidays, early closes, late opens, and
provider maintenance windows are not modeled yet.

## HTTP Error Response

Request-level and system-level HTTP errors use this shape:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `error` | Error object | yes | Error envelope. |

Error object:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `code` | string enum | yes | Stable machine-readable code. |
| `message` | string | yes | Sanitized human-readable message. |
| `details` | object or null | yes | Optional structured context. May be `null`. |

```json
{
  "error": {
    "code": "UNSUPPORTED_TIMEFRAME",
    "message": "Timeframe is not supported by this gateway.",
    "details": {
      "timeframe": "2m"
    }
  }
}
```

HTTP error codes:

| Code | HTTP status | Applies to | Meaning |
| --- | --- | --- | --- |
| `INVALID_SYMBOLS` | `400` | `/v1/quotes`, `/v1/stream` | Missing or empty `symbols`. |
| `TOO_MANY_SYMBOLS` | `400` | `/v1/quotes`, `/v1/stream` | More than `MAX_QUOTE_SYMBOLS` distinct symbols. |
| `UNSUPPORTED_SYMBOL` | `400` | `/v1/candles`; per-symbol in `/v1/quotes`; close reason in `/v1/stream` | Unknown or disabled symbol. |
| `UNSUPPORTED_TIMEFRAME` | `400` | `/v1/candles`; close reason in `/v1/stream` | Unknown timeframe. |
| `INVALID_TIME_RANGE` | `400` | `/v1/candles` | Missing, invalid, unaligned, inverted, or too-wide time range. |
| `DATABASE_UNAVAILABLE` | `503` | database-backed endpoints | Gateway cannot query PostgreSQL. |
| `PROVIDER_UNAVAILABLE` | `503` | REST provider failures; close reason or status event in `/v1/stream` | Upstream provider is unavailable. |
| `DATA_STALE` | `503` or quote item error | Fresh data is required but only stale data exists. |
| `INTERNAL_ERROR` | `500` | all endpoints | Unexpected gateway failure. |

## WebSocket Stream

```text
WS /v1/stream?symbols=BTC%2FUSD,ETH%2FUSD&timeframe=1m
```

The stream emits quote, candle, and status JSON events. There is no application-level subscribe
message after connection; subscription parameters are passed in the query string. Application-level
inbound messages are not part of the public contract.

### Query Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `symbols` | comma-separated string | yes | One or more canonical symbols. Whitespace is trimmed; duplicates are de-duplicated. |
| `timeframe` | string enum | yes | Candle timeframe for all requested symbols. One of `1m`, `5m`, `15m`, `1h`, `1d`. |

Each requested symbol subscribes to both `quote` and `candle` channels.

### Quote Event

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `type` | string enum | yes | Always `quote`. |
| `symbol` | string | yes | Canonical symbol. |
| `price` | decimal string | yes | Latest normalized stream price. |
| `receivedAt` | UTC datetime string | yes | Time the gateway received or normalized the event. |

```json
{
  "type": "quote",
  "symbol": "BTC/USD",
  "price": "64196.19000000",
  "receivedAt": "2026-06-22T02:59:19.184926Z"
}
```

### Candle Event

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `type` | string enum | yes | Always `candle`. |
| `symbol` | string | yes | Canonical symbol. |
| `timeframe` | string enum | yes | Requested timeframe. |
| `openTime` | UTC datetime string | yes | Candle bucket start, inclusive. |
| `closeTime` | UTC datetime string | yes | Candle bucket end timestamp. |
| `open` | decimal string | yes | Opening price for the bucket. |
| `high` | decimal string | yes | Highest price for the bucket. |
| `low` | decimal string | yes | Lowest price for the bucket. |
| `close` | decimal string | yes | Latest or closing price for the bucket. |
| `volume` | decimal string | yes | Stream volume when available; Twelve Data-derived stream candles use `0`. |
| `complete` | boolean | yes | `true` when the candle is closed, otherwise `false`. |
| `receivedAt` | UTC datetime string | yes | Time the gateway emitted or normalized the candle event. |

```json
{
  "type": "candle",
  "symbol": "BTC/USD",
  "timeframe": "1m",
  "openTime": "2026-06-22T02:59:00Z",
  "closeTime": "2026-06-22T02:59:59.999000Z",
  "open": "64100.00",
  "high": "64200.00",
  "low": "64090.00",
  "close": "64196.19",
  "volume": "12.345",
  "complete": false,
  "receivedAt": "2026-06-22T02:59:19.184926Z"
}
```

### Status Event

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `type` | string enum | yes | Always `status`. |
| `state` | string enum | yes | Stream state listed below. |
| `symbols` | array of strings | yes | Affected canonical symbols. |
| `channels` | array of string enums | yes | Affected channels. Values are `quote` and/or `candle`. |
| `observedAt` | UTC datetime string | yes | Time the gateway observed the state. |
| `code` | string enum | only when `state` is `ERROR` | Stable machine-readable error code. |
| `message` | string | only when `state` is `ERROR` | Sanitized human-readable error message. |

Stream states:

| State | Meaning |
| --- | --- |
| `CONNECTING` | Gateway is opening or reopening upstream provider interests. |
| `SUBSCRIBED` | Gateway is receiving fresh events for the active subscription. |
| `STALE` | No fresh upstream event has arrived within the configured freshness threshold. |
| `RECONNECTING` | Provider connection is reconnecting; events may pause. |
| `MARKET_CLOSED` | Requested candle channel is outside the configured market session. |
| `ERROR` | Gateway cannot serve the affected stream interests. |

```json
{
  "type": "status",
  "state": "SUBSCRIBED",
  "symbols": ["BTC/USD", "ETH/USD"],
  "channels": ["quote", "candle"],
  "observedAt": "2026-06-22T02:59:19.184926Z"
}
```

```json
{
  "type": "status",
  "state": "ERROR",
  "symbols": ["BTC/USD"],
  "channels": ["quote"],
  "observedAt": "2026-06-22T02:59:19.184926Z",
  "code": "PROVIDER_UNAVAILABLE",
  "message": "The market data provider is temporarily unavailable."
}
```

### WebSocket Close Codes

| Close code | Reason | Meaning |
| --- | --- | --- |
| `1000` | empty or normal close | Normal client/server close. |
| `1008` | `INVALID_SYMBOLS`, `TOO_MANY_SYMBOLS`, `UNSUPPORTED_SYMBOL`, `UNSUPPORTED_TIMEFRAME` | Invalid subscription request. |
| `1011` | `DATABASE_UNAVAILABLE` or `PROVIDER_UNAVAILABLE` | Gateway cannot initialize or continue the stream due to backend/provider failure. |
| `1012` | `SERVICE_RESTART` | Gateway is shutting down or restarting. |
| `1013` | `CLIENT_TOO_SLOW` | Client could not consume events fast enough and its downstream queue filled. |

## Client Implementation Checklist

- Discover enabled symbols with `GET /v1/symbols` instead of hard-coding the registry.
- URL-encode symbols in query strings.
- Treat decimal fields as strings and convert to fixed-point decimal types client-side.
- Handle partial success in `/v1/quotes`; do not assume an empty `quotes` array means HTTP failure.
- Handle empty candle arrays as valid responses.
- Reconnect WebSocket streams with backoff after `1011`, `1012`, or network disconnects.
- Treat `MARKET_CLOSED` as a non-error state for candle channels.
- Ignore provider fields outside `/v1/symbols`; quotes, candles, and stream events are provider-agnostic by contract.
