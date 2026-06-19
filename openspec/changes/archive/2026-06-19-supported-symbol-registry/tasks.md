## 1. Dependencies and Configuration

- [x] 1.1 Add the locked SQLAlchemy, asyncpg, and Alembic dependencies and refresh `uv.lock`.
- [x] 1.2 Add typed optional database URL and pool settings without making application startup depend on PostgreSQL.
- [x] 1.3 Add `.env.example` with non-secret `DATABASE_URL`, pool, and `TEST_DATABASE_URL` placeholders.

## 2. Database Foundation

- [x] 2.1 Add the async SQLAlchemy engine, session factory, declarative base, and FastAPI session dependency.
- [x] 2.2 Configure Alembic for the async PostgreSQL metadata and environment-provided database URL.
- [x] 2.3 Add the `supported_symbols` SQLAlchemy model with canonical and provider uniqueness constraints.
- [x] 2.4 Create the initial migration that creates `supported_symbols` and idempotently seeds the BTC/USD and ETH/USD Binance Spot mappings.
- [x] 2.5 Add a downgrade that removes the registry table introduced by the migration.

## 3. Registry Domain and API

- [x] 3.1 Add domain symbol records and a repository contract that does not expose SQLAlchemy models.
- [x] 3.2 Implement the PostgreSQL repository query for enabled symbols ordered by canonical symbol.
- [x] 3.3 Add a symbol service that obtains registry data exclusively through the repository boundary.
- [x] 3.4 Add Pydantic response DTOs with the documented camelCase fields.
- [x] 3.5 Implement and register `GET /v1/symbols`.
- [x] 3.6 Map missing configuration and database query failures to a sanitized HTTP 503 `DATABASE_UNAVAILABLE` response.
- [x] 3.7 Verify `GET /health` remains independent of database configuration and connectivity.

## 4. Verification

- [x] 4.1 Add unit tests for service delegation, enabled-symbol serialization, empty results, ordering, and database error mapping.
- [x] 4.2 Add PostgreSQL integration tests for migration schema, exact seed mappings, idempotent seed behavior, constraints, disabled-record filtering, and persisted mapping changes.
- [x] 4.3 Gate PostgreSQL integration tests on `TEST_DATABASE_URL` and document the explicit skip behavior when it is absent.
- [x] 4.4 Run pytest, Ruff checks and formatting, and strict mypy; run the PostgreSQL integration suite when database configuration is available.

## 5. Documentation

- [x] 5.1 Update the product and system design documents so the supported-symbol registry is included in the persistence model.
- [x] 5.2 Update README setup instructions with placeholder database configuration, Alembic upgrade/downgrade commands, and symbol endpoint verification.
