# Repository Guidelines

## Project Structure & Module Organization

This repository contains the FastAPI scaffold and design documentation for the Signapse Market Data Gateway crypto MVP.

- `docs/spec.md` is the product and API contract source of truth.
- `docs/system-design.md` describes architecture, components, data flow, persistence, and rollout plan.
- `docs/tech-stack.md` records stack decisions and implementation tooling.

- `app/` for FastAPI source code.
- `app/api/` for HTTP and WebSocket routes.
- `app/domain/` for symbols, timeframes, models, and errors.
- `app/providers/` for Binance and future provider adapters.
- `app/db/` for SQLAlchemy models, sessions, and repositories.
- `tests/unit/` and `tests/integration/` for tests.
- `alembic/` for database migrations.

## Build, Test, and Development Commands

Use `uv` for dependency and command execution.

- `uv sync`: install locked dependencies.
- `uv run uvicorn app.main:app --reload`: run the local FastAPI server.
- `uv run pytest`: run the test suite.
- `uv run ruff check .`: lint the codebase.
- `uv run ruff format .`: format Python files.
- `uv run mypy app`: run static type checks.

Run `uv run alembic upgrade head` after configuring `DATABASE_URL`.

## Coding Style & Naming Conventions

Use Python 3.14.6, FastAPI 0.137.2, Pydantic 2.13.4, SQLAlchemy 2.0.51 async, and async-first I/O. Keep typed boundaries between API DTOs, domain models, provider adapters, and persistence.

Use 4-space indentation. Name modules `snake_case.py`, classes `PascalCase`, functions and variables `snake_case`, and constants `UPPER_SNAKE_CASE`. Store price and volume as `Decimal`; serialize API decimals as strings.

## Provider Integration Guidelines

When researching a market-data provider, check for an official, actively maintained SDK before designing direct HTTP or WebSocket calls. Prefer the official SDK when it supports the required APIs, Python version, async/concurrency model, timeout controls, and testability.

Keep every SDK behind an adapter in `app/providers/`. Do not expose SDK request models, response models, or exceptions to domain, service, or API layers. Normalize provider data into repository-owned domain models.

Use direct protocol integration only when the SDK is unavailable, incompatible, missing required functionality, or introduces a documented operational risk. Record that exception and its trade-offs in the relevant OpenSpec design or technical decision before implementation.

## Testing Guidelines

Use `pytest` with `pytest-asyncio` for async tests. Name test files `test_*.py` and test functions `test_<behavior>()`.

Prioritize registry validation, timeframe mapping, decimal serialization, freshness rules, error mapping, provider normalization, route behavior, and candle upserts. Target at least 80% overall coverage once implementation begins.

## Commit & Pull Request Guidelines

No usable Git history is available in this workspace, so use concise conventional-style commits:

- `docs: add system design`
- `feat: add quote endpoint`
- `test: cover Binance kline normalization`

Pull requests should include a summary, linked issue or task, test evidence, and notes for contract or migration changes. For API changes, update `docs/spec.md` and related design docs in the same PR.

## Security & Configuration Tips

Do not commit secrets or local `.env` files. Binance public market data does not require API keys for the MVP. Keep provider URLs, stale thresholds, cache TTLs, and database URLs configurable.
