# Signapse Market Data Gateway

FastAPI service for the Signapse crypto market data gateway.

## Getting Started

### Prerequisites

- Git
- `uv 0.11.22`

The project locks Python to `3.14.6`. `uv` will install the required Python
runtime automatically when it is not already available.

Install the locked `uv` version with the official Windows installer:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/0.11.22/install.ps1 | iex"
```

Close and reopen PowerShell, then confirm the installation:

```powershell
uv --version
```

If `uv` is still not recognized, add its default installation directory to
the current PowerShell session:

```powershell
$env:Path = "$HOME\.local\bin;$env:Path"
uv --version
```

Expected version:

```text
uv 0.11.22
```

### Install Dependencies

From the repository root:

```powershell
uv sync
```

This creates `.venv`, installs Python `3.14.6` when needed, and installs the
dependencies locked in `uv.lock`.

Binance integration uses the locked official `binance-sdk-spot==9.2.0` package.
The provider adapter offloads its synchronous REST operation from the ASGI event loop.

### Configure PostgreSQL

Copy the placeholders from `.env.example` into a local `.env` and replace them
with deployment-specific values:

```dotenv
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>
DATABASE_POOL_SIZE=5
DATABASE_POOL_MAX_OVERFLOW=5
DATABASE_POOL_TIMEOUT_SECONDS=5
BINANCE_REST_BASE_URL=https://api.binance.com
TWELVEDATA_API_KEYS=<twelve-data-api-key-2>,<twelve-data-api-key-3>
TWELVEDATA_REST_BASE_URL=https://api.twelvedata.com
TWELVEDATA_WS_HEARTBEAT_SECONDS=15
PROVIDER_HTTP_TIMEOUT_SECONDS=5
QUOTE_CACHE_TTL_SECONDS=10
QUOTE_STALE_AFTER_SECONDS=30
MAX_QUOTE_SYMBOLS=10
MAX_CANDLES_PER_REQUEST=1000
```

Apply the schema and seed the supported symbols:

```powershell
uv run alembic upgrade head
```

To roll back the registry migration:

```powershell
uv run alembic downgrade -1
```

### Start the API

```powershell
uv run uvicorn app.main:app --reload
```

The API is available at:

- Health check: <http://127.0.0.1:8000/health>
- Supported symbols: <http://127.0.0.1:8000/v1/symbols>
- Latest quotes: <http://127.0.0.1:8000/v1/quotes?symbols=BTC%2FUSD%2CETH%2FUSD>
- Historical candles: <http://127.0.0.1:8000/v1/candles?symbol=BTC%2FUSD&timeframe=1m&from=2026-06-19T00%3A00%3A00Z&to=2026-06-19T00%3A02%3A00Z>
- OpenAPI docs: <http://127.0.0.1:8000/docs>

For external client implementation details, including required fields, response types, WebSocket
events, and close codes, see [docs/api-contract.md](docs/api-contract.md).

Verify the health endpoint from another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "UP",
  "time": "2026-06-19T08:56:32.913050Z"
}
```

The `time` value is generated dynamically in UTC.

Set `TWELVEDATA_API_KEYS` as a comma-separated list. A single value is valid; duplicate and empty
values are ignored.

Fetch the two supported Binance-backed quotes:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/v1/quotes?symbols=BTC%2FUSD%2CETH%2FUSD"
```

Fetch the supported Twelve Data-backed Forex, commodity, US stock, and ETF quotes:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/v1/quotes?symbols=EUR%2FUSD%2CXAU%2FUSD%2CAAPL%2CWTI%2CSPY%2CQQQ"
```

Quote responses contain ordered `quotes` and per-symbol `errors`. Successful items expose only
the canonical `symbol`, decimal-string `price`, and gateway `receivedAt`. The application can
start and serve crypto quotes without Twelve Data keys; live Twelve Data refreshes require at least
one configured key.

Fetch an aligned half-open UTC candle range:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/v1/candles?symbol=BTC%2FUSD&timeframe=1m&from=2026-06-19T00%3A00%3A00Z&to=2026-06-19T00%3A02%3A00Z"
```

Fetch candles through the current request time by omitting `to`:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/v1/candles?symbol=WTI&timeframe=1h&from=2026-06-18T13%3A00%3A00Z"
```

The response still includes `to`, resolved to the exact UTC request time. Request boundaries do
not need to align to timeframe boundaries, and provider candle timestamps such as Twelve Data
hourly `:30` labels are preserved.

Fetch a Twelve Data-backed Forex candle range:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/v1/candles?symbol=EUR%2FUSD&timeframe=1m&from=2026-06-22T00%3A00%3A00Z&to=2026-06-22T00%3A05%3A00Z"
```

Fetch regular-session SPY candles:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/v1/candles?symbol=SPY&timeframe=1h&from=2026-06-22T14%3A00%3A00Z&to=2026-06-22T20%3A00%3A00Z"
```

Fetch WTI candles around its daily maintenance break:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/v1/candles?symbol=WTI&timeframe=1h&from=2026-06-22T20%3A00%3A00Z&to=2026-06-22T23%3A00%3A00Z"
```

Verify Forex weekend filtering with a Friday-to-Monday hourly range:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/v1/candles?symbol=EUR%2FUSD&timeframe=1h&from=2026-06-19T00%3A00%3A00Z&to=2026-06-22T00%3A00%3A00Z"
```

For this June 2026 example, New York is on EDT. Signapse excludes the closed Forex session from
Friday `2026-06-19T21:00:00Z` through Sunday `2026-06-21T21:00:00Z`, so the response should contain
Friday open-session candles through `20:00Z` and Sunday candles from `21:00Z` onward. Holidays,
early closes, late opens, and exceptional closures are intentionally not modeled yet.

The response exposes only canonical series context:

```json
{
  "symbol": "BTC/USD",
  "timeframe": "1m",
  "from": "2026-06-19T00:00:00Z",
  "to": "2026-06-19T00:02:00Z",
  "candles": [
    {
      "openTime": "2026-06-19T00:00:00Z",
      "closeTime": "2026-06-19T00:00:59.999000Z",
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

`assetClass`, `provider`, and `providerSymbol` remain internal. Requests are limited by
`MAX_CANDLES_PER_REQUEST`. Live Forex fills require
one configured Twelve Data key; fully persisted Forex ranges do not. Twelve Data Forex may omit volume, in
which case the API returns `"volume": "0"` as an unavailable-volume placeholder rather than a
measured zero-activity value.

### Backfill historical candles

Use the internal backfill command to pre-warm `market_data_candles` before user traffic requests a
range:

```powershell
uv run python -m app.backfill_candles --from 2026-06-19T00:00:00Z --to 2026-06-20T00:00:00Z --timeframes 1m,5m --symbols BTC/USD,ETH/USD
```

The command requires `DATABASE_URL` and the same provider configuration as `/v1/candles`.
It reads enabled registry symbols, splits ranges by `MAX_CANDLES_PER_REQUEST`, reuses the existing
repository-first candle service, fetches only missing ranges, and upserts only complete candles.

Optional filters:

```powershell
--symbols BTC/USD,EUR/USD
--providers BINANCE_SPOT,TWELVE_DATA,YFINANCE
--asset-classes CRYPTO,FOREX,ETF
```

Scheduler integration, persistent job status, distributed locking, and no-data tombstones are
intentionally deferred. Run one backfill process at a time; reruns are safe because candle upserts
are idempotent.

### Test WebSocket streams

Postman can test `WS /v1/stream` directly with a WebSocket request:

```text
ws://127.0.0.1:8000/v1/stream?symbols=BTC%2FUSD,EUR%2FUSD&timeframe=1m
```

Forex-only example:

```text
ws://127.0.0.1:8000/v1/stream?symbols=EUR%2FUSD,GBP%2FUSD&timeframe=1m
```

WTI and ETF example:

```text
ws://127.0.0.1:8000/v1/stream?symbols=WTI,SPY,QQQ&timeframe=1m
```

Expected status events keep the same shape:

```json
{
  "type": "status",
  "state": "CONNECTING",
  "symbols": ["BTC/USD", "EUR/USD"],
  "channels": ["quote", "candle"],
  "observedAt": "2026-06-22T00:00:00Z"
}
```

During a configured Forex, ETF, or WTI closed candle session, the candle channel can emit
`MARKET_CLOSED` instead of `STALE`. Quote events may still arrive if Twelve Data sends prices.
Twelve Data stream candles are derived from price ticks and use decimal zero volume;
`/v1/candles` remains the authoritative backfill path. Holidays, early closes, late opens, and
exceptional closures are not modeled yet.

## Development Checks

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

To apply formatting:

```powershell
uv run ruff format .
```

PostgreSQL integration tests require `TEST_DATABASE_URL` pointing to a disposable
database. They are skipped explicitly when it is absent:

```powershell
$env:TEST_DATABASE_URL="postgresql+asyncpg://<user>:<password>@<host>:<port>/<test_database>"
uv run pytest -m integration
```
