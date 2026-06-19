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
PROVIDER_HTTP_TIMEOUT_SECONDS=5
QUOTE_CACHE_TTL_SECONDS=10
QUOTE_STALE_AFTER_SECONDS=30
MAX_QUOTE_SYMBOLS=10
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
- OpenAPI docs: <http://127.0.0.1:8000/docs>

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

Fetch the two supported Binance-backed quotes:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/v1/quotes?symbols=BTC%2FUSD%2CETH%2FUSD"
```

Quote responses contain ordered `quotes` and per-symbol `errors`. Price values are
decimal strings; `volume` and `providerTime` are `null` in this MVP.

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
