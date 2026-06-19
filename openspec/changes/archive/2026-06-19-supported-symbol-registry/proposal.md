## Why

The gateway needs a durable source of truth for supported market symbols before quote and
candle capabilities can validate requests consistently. Adding the PostgreSQL-backed registry
now establishes the database foundation and delivers the first complete seed-to-API flow.

## What Changes

- Add PostgreSQL connectivity through SQLAlchemy async sessions and `asyncpg`.
- Add Alembic migrations for a supported-symbol registry.
- Seed exactly `BTC/USD` and `ETH/USD` with their Binance Spot mappings.
- Add a repository and service boundary for reading enabled symbols.
- Expose enabled symbols through `GET /v1/symbols` using the existing API contract.
- Add placeholder database configuration without committing deployment credentials.
- Preserve `GET /health` as independent from database availability.

## Capabilities

### New Capabilities

- `supported-symbol-registry`: Persist, seed, query, and expose the gateway's enabled canonical
  symbols and provider mappings.

### Modified Capabilities

None.

## Impact

- Adds PostgreSQL 18.4, SQLAlchemy 2.0.51 async, asyncpg 0.31.0, and Alembic 1.18.4 to the
  runnable service.
- Adds database configuration, models, migrations, repository/service modules, and the
  `/v1/symbols` route.
- Requires a PostgreSQL database and migration execution before the symbol endpoint is usable.
- Adds PostgreSQL-backed integration tests while keeping unit tests independent of a database.
