# Signapse Market Data Gateway Crypto MVP - Tech Stack Research

Date: 2026-06-19

This document records the recommended technology stack for the crypto MVP described in `docs/spec.md` and refined in `docs/system-design.md`.

## 1. Recommendation Summary

| Concern | Recommended choice | Why |
| --- | --- | --- |
| Language | Python 3.14.6 | Latest stable runtime baseline, locked from this point forward. |
| API framework | FastAPI 0.137.2 | Native ASGI, typed DTOs, OpenAPI, HTTP + WebSocket support. |
| Runtime server | Uvicorn 0.49.0 | Standard ASGI server fit for FastAPI. |
| DTO validation | Pydantic 2.13.4 | Type-hint driven validation, serialization, JSON Schema support. |
| Settings | pydantic-settings 2.14.1 | Typed environment configuration. |
| REST client | HTTPX 0.28.1 | Async HTTP client with timeout support and HTTP/2 option. |
| Provider WebSocket client | websockets 16.0 | Focused WebSocket client/server library built for asyncio. |
| Database | PostgreSQL 18.4 | Reliable relational store for candle cache and future asset metadata. |
| DB driver | asyncpg 0.31.0 | PostgreSQL driver designed for Python asyncio. |
| ORM/query layer | SQLAlchemy 2.0.51 | Mature Core/ORM APIs with asyncio-compatible engine/session support. |
| Migration | Alembic 1.18.4 | SQLAlchemy-native database migration tool. |
| In-memory cache | Process-local Python cache | Enough for two-symbol MVP; Redis deferred. |
| Logging | structlog 26.1.0 + stdlib logging | Structured logs with context fields for provider, symbol, timeframe, request IDs. |
| Metrics | prometheus-client 0.25.0 | Simple counters, gauges, histograms exposed through HTTP. |
| Test runner | pytest 9.1.0 | Readable unit/integration tests and strong plugin ecosystem. |
| Async test support | pytest-asyncio 1.4.0 | Async pytest support. |
| HTTPX mocking | respx 0.23.1 | Mock provider REST calls in adapter tests. |
| Coverage | coverage.py 7.14.1 | Coverage reporting for test quality gates. |
| Lint/format | Ruff 0.15.18 | Fast linter and formatter with one configuration surface. |
| Type checking | mypy 2.1.0 | Static type checks for DTOs, adapters, repositories, and service boundaries. |
| Dependency manager | uv 0.11.22 | Fast project/dependency manager with lockfile support. |
| Container/deploy | Docker Compose | Matches the existing server deployment environment. |

## 2. Locked Versions

These versions are locked as the project baseline from 2026-06-19. Use latest stable at the time of locking, but commit `uv.lock` so production and CI do not drift.

| Tool/package | Version |
| --- | --- |
| Python | `3.14.6` |
| Docker Python image | `python:3.14.6-slim` |
| PostgreSQL | `18.4` |
| Docker PostgreSQL image | `postgres:18.4` |
| FastAPI | `0.137.2` |
| Uvicorn | `0.49.0` |
| Pydantic | `2.13.4` |
| pydantic-settings | `2.14.1` |
| HTTPX | `0.28.1` |
| websockets | `16.0` |
| asyncpg | `0.31.0` |
| SQLAlchemy | `2.0.51` |
| Alembic | `1.18.4` |
| structlog | `26.1.0` |
| prometheus-client | `0.25.0` |
| pytest | `9.1.0` |
| pytest-asyncio | `1.4.0` |
| respx | `0.23.1` |
| coverage.py | `7.14.1` |
| Ruff | `0.15.18` |
| mypy | `2.1.0` |
| uv | `0.11.22` |

## 3. Runtime and Application Layer

### Python

Use Python 3.14.6 as the initial production baseline.

Rationale:

- The project starts from the latest stable Python line available at stack-lock time.
- Use `requires-python = "==3.14.*"` initially.
- Commit `.python-version` with `3.14.6`.

Fallback:

- If a dependency lacks Python 3.14 wheels during implementation, pause and decide explicitly before downgrading. Do not silently switch runtime versions.

### FastAPI

FastAPI is the right API framework for this MVP because the gateway contract is typed and HTTP/WebSocket based.

Use it for:

- `/health`
- `/v1/symbols`
- `/v1/quotes`
- `/v1/candles`
- `/v1/stream`
- OpenAPI generation for HTTP endpoints
- Pydantic response models
- Lifespan startup/shutdown hooks for shared clients and lazy provider stream cleanup

Install recommendation:

```text
fastapi[standard-no-fastapi-cloud-cli]==0.137.2
```

Reason:

- Standard dependencies include server/test-friendly integrations such as Uvicorn and HTTPX.
- Excluding FastAPI Cloud CLI keeps the service dependency tree leaner.

### Uvicorn

Use Uvicorn as the ASGI server.

Local command:

```text
uv run uvicorn app.main:app --reload
```

Production command:

```text
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For the MVP, run one worker per process because in-memory quote/current-candle caches are process-local. Scale horizontally only after moving shared live state to Redis or another pub/sub layer.

## 4. Contract and Data Modeling

### Pydantic v2

Use Pydantic for external API DTOs and config validation.

Patterns:

- Keep domain models separate from API response models.
- Store monetary/market numeric values internally as `Decimal`.
- Serialize API-facing decimals as strings, matching the spec.
- Use explicit field aliases for external camelCase fields such as `assetClass`, `providerSymbol`, `providerTime`, and `receivedAt`.
- Use strict validation for public request models where practical.

Recommended packages:

```text
pydantic==2.13.4
pydantic-settings==2.14.1
```

### Decimal Handling

Rules:

- Provider string numbers become Python `Decimal` immediately.
- Domain and DB layers never use `float` for price or volume.
- API responses serialize decimal fields as strings.
- PostgreSQL stores OHLCV fields as `NUMERIC`.

## 5. Provider Integration

### Binance REST

Use HTTPX async client for provider REST calls.

Initial endpoints:

- `GET /api/v3/ticker/price` for latest price fallback or cache fill.
- Defer `GET /api/v3/ticker/24hr`; quote `volume` is `null` in the MVP.
- `GET /api/v3/klines` for candle backfill and historical cache fill.

Important constraints:

- Binance kline intervals are case-sensitive; `1M` is month, while our public contract uses `1mo`.
- `startTime` and `endTime` are interpreted in UTC by Binance.
- Klines are uniquely identified by open time, matching our DB uniqueness model.
- Always pass explicit symbols. Never request all symbols in production paths.

### Binance WebSocket

Use the `websockets` package for upstream provider streams.

Initial streams:

```text
<symbol>@ticker
<symbol>@kline_<interval>
```

Examples from the current spec:

```text
btcusd@ticker
ethusd@ticker
btcusd@kline_1m
ethusd@kline_1m
```

Provider-symbol decision:

- Keep canonical symbols as `BTC/USD` and `ETH/USD`.
- Map them to Binance Spot `BTCUSD` and `ETHUSD` for the MVP.
- Add a startup or CI smoke check against Binance exchange metadata so unsupported provider symbols fail loudly.
- Open upstream WebSocket streams lazily when downstream clients subscribe, not at app startup.

## 6. Persistence

### PostgreSQL

Use PostgreSQL for closed candle cache.

Reason:

- The MVP only needs relational candle persistence.
- `NUMERIC` is appropriate for exact price/volume values.
- Unique indexes can enforce the candle identity rule.

Initial database object:

```text
market_data_candles
```

Primary uniqueness:

```text
unique(provider, provider_symbol, timeframe, open_time)
```

### SQLAlchemy 2 Async

Use SQLAlchemy 2 async for repository access.

Patterns:

- One async engine per process.
- One async session per request or operation.
- Keep SQLAlchemy models in `app/db/models.py`.
- Keep query/upsert behavior in repository classes/functions.
- Avoid leaking ORM models into API DTOs.

Install recommendation:

```text
sqlalchemy[asyncio]==2.0.51
asyncpg==0.31.0
```

### Alembic

Use Alembic for schema migrations.

Patterns:

- Migration files are the source of truth for DB shape.
- Use explicit migration names.
- Keep async app runtime separate from migration execution.

## 7. Caching and State

### MVP Cache

Use process-local in-memory cache for:

- Latest quote per canonical symbol.
- Current forming candle per `(symbol, timeframe)`.
- Optional provider health state.

Concurrency:

- Wrap mutation in a small cache abstraction.
- Use `asyncio.Lock` only inside cache classes, not scattered across services.

### Deferred Redis

Do not add Redis in the first MVP unless any of these become true:

- Multiple application replicas must share latest quote state.
- WebSocket fanout must work across replicas.
- Provider stream consumption must be centralized.
- Cache loss during process restart becomes unacceptable.

## 8. Observability

### Logging

Use stdlib logging configured for JSON output through structlog.

Required fields:

- `request_id`
- `symbol`
- `provider`
- `provider_symbol`
- `timeframe`
- `from`
- `to`
- `error_code`
- `upstream_latency_ms`

### Metrics

Use Prometheus Python client.

Initial metrics:

- `provider_rest_requests_total`
- `provider_rest_request_duration_seconds`
- `provider_rest_errors_total`
- `provider_ws_reconnects_total`
- `stream_clients_active`
- `quote_cache_hits_total`
- `quote_cache_misses_total`
- `candle_cache_hits_total`
- `candle_cache_misses_total`
- `stale_quotes_total`

Expose metrics on:

```text
GET /metrics
```

Keep `/metrics` private to infrastructure.

## 9. Testing Stack

### pytest

Use pytest for all unit and integration tests.

Recommended packages:

```text
pytest==9.1.0
pytest-asyncio==1.4.0
httpx==0.28.1
respx==0.23.1
```

Test layers:

- Unit: registry, timeframe mapping, freshness, decimal serialization, error mapping.
- Adapter: Binance REST payload normalization and WebSocket payload normalization.
- Route: FastAPI HTTP response shape and validation behavior.
- Repository: candle upsert/query behavior against a test PostgreSQL database.
- WebSocket: subscription validation and event fanout.

### coverage.py

Use coverage.py for coverage reports.

Suggested gate for MVP:

```text
80% line coverage overall
90%+ coverage for domain validation, DTO serialization, and provider normalization
```

## 10. Developer Tooling

### uv

Use uv 0.11.22 for dependency management and repeatable local commands.

Expected files:

```text
pyproject.toml
uv.lock
.python-version
```

Recommended local commands:

```text
uv sync
uv run uvicorn app.main:app --reload
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy app
```

### Ruff

Use Ruff for linting and formatting.

Recommended baseline:

- Enable formatter.
- Enable import sorting.
- Enable pyupgrade, bugbear-style rules, and common error rules.
- Avoid preview rules until the codebase has stabilized.

### mypy

Use mypy for static type checking.

Recommended mode:

- Start strict on `app/domain`, `app/providers`, and `app/services`.
- Allow slightly looser settings around SQLAlchemy models if needed.
- Treat adapter interfaces as typed contracts.

## 11. Packaging and Deployment

### Docker Compose

Use a slim Python base image matching the selected Python baseline.

Production shape:

```text
python:3.14.6-slim
postgres:18.4
```

Container responsibilities:

- Install locked dependencies.
- Run Alembic migrations as a separate release step, not automatically inside app startup.
- Start Uvicorn.
- Expose port `8000`.

Deployment shape:

- `docker-compose.yml` should define the gateway service and PostgreSQL `18.4` service unless the server already provides PostgreSQL.
- Mount configuration through environment variables, not committed `.env` secrets.
- Keep the service internal-only at first; add reverse proxy auth/rate limiting before any public exposure.

### Environment

Minimum runtime variables:

```text
APP_ENV
LOG_LEVEL
DATABASE_URL
BINANCE_REST_BASE_URL
BINANCE_WS_BASE_URL
QUOTE_STALE_AFTER_SECONDS
QUOTE_CACHE_TTL_SECONDS
MAX_CANDLE_RANGE_DAYS
MAX_QUOTE_SYMBOLS
PROVIDER_HTTP_TIMEOUT_SECONDS
```

## 12. Dependency Groups

Suggested `pyproject.toml` grouping:

```text
[project.dependencies]
fastapi[standard-no-fastapi-cloud-cli]==0.137.2
pydantic==2.13.4
pydantic-settings==2.14.1
httpx==0.28.1
websockets==16.0
sqlalchemy[asyncio]==2.0.51
asyncpg==0.31.0
alembic==1.18.4
structlog==26.1.0
prometheus-client==0.25.0

[dependency-groups.dev]
pytest==9.1.0
pytest-asyncio==1.4.0
respx==0.23.1
coverage==7.14.1
ruff==0.15.18
mypy==2.1.0
```

## 13. Decisions

### Accepted

- Python/FastAPI async stack.
- Latest stable dependency versions are locked in this document and should be reflected in `pyproject.toml` and `uv.lock`.
- Pydantic v2 for DTOs and settings.
- HTTPX for REST provider calls.
- `websockets` for provider streams.
- Canonical `BTC/USD` and `ETH/USD` mapped to Binance `BTCUSD` and `ETHUSD`.
- Quote `volume` returns `null` in the MVP.
- Multi-symbol quote failures return per-symbol errors.
- Upstream WebSocket streams open only when clients subscribe.
- PostgreSQL + SQLAlchemy async + Alembic for candle cache.
- Process-local cache for MVP.
- uv + Ruff + mypy + pytest for developer workflow.
- Docker Compose deployment on the existing server.

### Deferred

- Redis shared cache/pub-sub.
- TimescaleDB.
- OpenTelemetry tracing.
- Public auth and quota middleware.
- Multi-provider routing engine.
- Provider fallback strategy.

### Needs Validation Before Coding

- Whether `/v1/quotes` may return stale data with `stale = true`, or should fail with `DATA_STALE`.

## 14. Primary References

- Python documentation: https://docs.python.org/3/
- FastAPI documentation: https://fastapi.tiangolo.com/
- Pydantic documentation: https://docs.pydantic.dev/latest/
- Uvicorn documentation: https://www.uvicorn.org/
- HTTPX documentation: https://www.python-httpx.org/
- websockets documentation: https://websockets.readthedocs.io/
- Binance Spot market data REST: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints
- Binance Spot WebSocket streams: https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams
- PostgreSQL numeric types: https://www.postgresql.org/docs/current/datatype-numeric.html
- SQLAlchemy asyncio: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Alembic documentation: https://alembic.sqlalchemy.org/en/latest/
- asyncpg documentation: https://magicstack.github.io/asyncpg/current/
- uv documentation: https://docs.astral.sh/uv/
- Ruff documentation: https://docs.astral.sh/ruff/
- mypy documentation: https://mypy.readthedocs.io/en/stable/
- pytest documentation: https://docs.pytest.org/en/stable/
- coverage.py documentation: https://coverage.readthedocs.io/en/latest/
- structlog documentation: https://www.structlog.org/en/stable/
- Prometheus Python client: https://prometheus.github.io/client_python/

