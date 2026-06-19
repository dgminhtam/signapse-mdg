## Why

The repository currently contains the Signapse Market Data Gateway contract and architecture documents, but no runnable service skeleton. A minimal FastAPI scaffold with `/health` creates the first executable slice so later market-data capabilities can be added against a real application boundary.

## What Changes

- Add a Python/FastAPI project scaffold managed by `uv`.
- Add an ASGI application entrypoint at `app.main:app`.
- Add `GET /health` as a lightweight process health endpoint matching the documented API contract.
- Add baseline configuration, UTC time handling, and route tests needed to verify the scaffold.
- Add baseline linting, formatting, and type-check configuration for future implementation work.

## Capabilities

### New Capabilities

- `service-health`: Exposes gateway process health and current UTC gateway time through `GET /health`.

### Modified Capabilities

- None.

## Impact

- Adds initial source layout under `app/`.
- Adds tests under `tests/`.
- Adds Python project metadata and tool configuration in `pyproject.toml` and `.python-version`.
- Establishes the local development command path documented in `docs/tech-stack.md`: `uv sync`, `uv run uvicorn app.main:app --reload`, `uv run pytest`, `uv run ruff check .`, and `uv run mypy app`.
- Does not introduce Binance provider calls, PostgreSQL/Alembic, WebSocket streaming, Docker Compose, authentication, or quote/candle APIs.
