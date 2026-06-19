## Context

The service currently exposes only `GET /health` and has no database layer. The product
contract fixes the canonical symbols to `BTC/USD` and `ETH/USD`, mapped to Binance Spot
symbols `BTCUSD` and `ETHUSD`. Future quote, candle, and stream capabilities need one
authoritative registry for validation and provider mapping.

PostgreSQL 18.4 and the async SQLAlchemy stack are already locked in the project documentation.
Deployment credentials are not yet available, and the existing health capability requires the
process to boot and serve `/health` without database configuration.

## Goals / Non-Goals

**Goals:**

- Establish async PostgreSQL connectivity and Alembic migrations.
- Persist and seed the two supported symbol mappings.
- Return enabled symbols through `GET /v1/symbols`.
- Keep database access behind repository and service boundaries.
- Allow the application and `/health` to run before database configuration is supplied.

**Non-Goals:**

- Quote, candle, or WebSocket provider integration.
- Administrative symbol mutation endpoints.
- Automatic Binance symbol discovery or synchronization.
- Multiple provider mappings per canonical symbol.
- Database readiness reporting from `GET /health`.

## Decisions

### Store the registry in one relational table

Create `supported_symbols` with:

- `id BIGINT` primary key
- `symbol TEXT` unique and non-null
- `asset_class TEXT` non-null
- `provider TEXT` non-null
- `provider_symbol TEXT` non-null
- `enabled BOOLEAN` non-null with a true default
- `created_at` and `updated_at` as timezone-aware timestamps
- a unique constraint on `(provider, provider_symbol)`

A normalized asset/provider schema was considered, but it adds joins and management concepts
that the two-symbol, single-provider MVP does not need. The repository boundary permits a later
schema change without changing the HTTP contract.

### Seed symbols in the schema migration

The initial Alembic revision creates the table and inserts exactly:

| symbol | asset_class | provider | provider_symbol |
| --- | --- | --- | --- |
| `BTC/USD` | `CRYPTO` | `BINANCE_SPOT` | `BTCUSD` |
| `ETH/USD` | `CRYPTO` | `BINANCE_SPOT` | `ETHUSD` |

The seed uses PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` so applying the seed logic is
idempotent. Application-startup seeding was rejected because it hides deployment state,
requires write privileges during every boot, and can race across replicas.

### Keep runtime database configuration optional at process startup

Add typed settings for an optional `DATABASE_URL` and pool tuning values. `.env.example`
contains only placeholders. The async engine and session factory are created only when a
database-backed dependency is requested.

This preserves the independent `/health` contract. `GET /v1/symbols` returns the stable
`DATABASE_UNAVAILABLE` error with HTTP 503 when configuration is absent or the query cannot
reach PostgreSQL. Alembic commands require a resolved database URL and fail explicitly without
one.

### Separate API, service, repository, and persistence models

The route depends on a symbol service. The service depends on a repository interface and
returns domain symbol records. SQLAlchemy models remain private to the database layer, while
Pydantic response models own camelCase serialization.

The repository selects only `enabled = true` rows and orders by canonical `symbol` ascending.
No in-memory fallback registry is used because it would create two competing sources of truth.

### Use PostgreSQL in integration tests

Repository and migration behavior is tested against PostgreSQL, not SQLite, because conflict
handling, timestamp behavior, async driver semantics, and constraints are PostgreSQL-specific.
Service and route unit tests use repository substitutes and require no database.

## Risks / Trade-offs

- [The symbol endpoint is unavailable until migrations and configuration are ready] -> Return
  a stable 503 error and document the migration-before-start deployment order.
- [Seed data can drift from the product contract] -> Assert exact mappings in migration and API
  integration tests.
- [Optional database configuration defers failure until a database endpoint is called] -> Log
  configuration state at startup without exposing credentials and fail clearly at the boundary.
- [A single-table model may not fit multi-provider routing later] -> Keep mapping access behind
  the repository and service interfaces.
- [Migration seed updates could overwrite deliberate operational edits] -> Limit the initial
  upsert to the fixed identity and mapping fields; future symbol changes require explicit
  migrations.

## Migration Plan

1. Supply `DATABASE_URL` in the target environment.
2. Run `alembic upgrade head` to create and seed `supported_symbols`.
3. Verify the two enabled records and their provider mappings.
4. Deploy the application with the same database configuration.
5. Verify `/health` and `/v1/symbols`.

Rollback uses `alembic downgrade -1`, which drops the registry table introduced by this change.
Because the table contains only seed metadata in this scope, no data export is required before
rollback.

## Open Questions

None for this change. Administrative management and multi-provider modeling remain deferred.
