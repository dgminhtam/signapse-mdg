## 1. Project Setup

- [x] 1.1 Add `.python-version` with the locked Python `3.14.6` baseline.
- [x] 1.2 Add `pyproject.toml` with `requires-python = "==3.14.*"`.
- [x] 1.3 Add pinned runtime dependencies: `fastapi[standard-no-fastapi-cloud-cli]==0.137.2`, `pydantic==2.13.4`, and `pydantic-settings==2.14.1`.
- [x] 1.4 Add pinned dev dependencies: `pytest==9.1.0`, `pytest-asyncio==1.4.0`, `httpx==0.28.1`, `ruff==0.15.18`, and `mypy==2.1.0`.
- [x] 1.5 Configure Ruff and mypy baselines in `pyproject.toml`.
- [x] 1.6 Run `uv sync` with uv `0.11.22` to resolve dependencies and generate `uv.lock`.

## 2. FastAPI Scaffold

- [x] 2.1 Create the initial `app/` package structure.
- [x] 2.2 Add `app.main:app` as the FastAPI application entrypoint.
- [x] 2.3 Add a health router under `app/api/routes_health.py`.
- [x] 2.4 Add a UTC time helper under `app/core/time.py`.
- [x] 2.5 Wire the health router into the FastAPI application.

## 3. Health Endpoint Behavior

- [x] 3.1 Implement `GET /health` with HTTP status `200`.
- [x] 3.2 Return response body fields `status` and `time`.
- [x] 3.3 Ensure `status` is always `UP` while the process can serve the route.
- [x] 3.4 Ensure `time` is an ISO-8601 UTC timestamp.
- [x] 3.5 Keep `/health` independent from Binance, PostgreSQL, WebSocket streams, and market-data caches.

## 4. Tests and Verification

- [x] 4.1 Add route tests for successful `GET /health`.
- [x] 4.2 Add assertions for response shape, `UP` status, and UTC timestamp parseability.
- [x] 4.3 Run `uv run pytest`.
- [x] 4.4 Run `uv run ruff check .`.
- [x] 4.5 Run `uv run mypy app`.
- [x] 4.6 Start `uv run uvicorn app.main:app --reload` and confirm `/health` is served.
