## 1. Runtime Configuration and Dependencies

- [x] 1.1 Move locked `httpx==0.28.1` from the development group to runtime dependencies and refresh `uv.lock`.
- [x] 1.2 Add validated settings for Binance REST base URL, provider timeout, quote cache TTL, stale threshold, and maximum quote symbols.
- [x] 1.3 Add the non-secret quote settings and documented defaults to `.env.example`.
- [x] 1.4 Add a FastAPI lifespan-managed shared HTTPX async client with dependency wiring that can be overridden in tests.

## 2. Quote Domain and Binance Adapter

- [x] 2.1 Add immutable quote and per-symbol error domain models using `Decimal` and timezone-aware datetimes.
- [x] 2.2 Define a provider protocol for batched latest-price retrieval without exposing Binance response models.
- [x] 2.3 Implement the Binance Spot adapter using one `/api/v3/ticker/price` batch request for all requested provider symbols.
- [x] 2.4 Validate Binance status and payloads, including duplicate, unexpected, missing, non-finite, zero, and negative prices, and map failures to sanitized provider errors.
- [x] 2.5 Add adapter unit tests with HTTPX `MockTransport` for valid batches, partial malformed payloads, HTTP failures, and transport timeouts.

## 3. Cache and Quote Service

- [x] 3.1 Implement a process-local quote cache keyed by canonical symbol with lock-protected reads, writes, age calculation, and refresh coalescing.
- [x] 3.2 Implement request parsing that trims symbols, rejects missing or empty input, deduplicates in first-occurrence order, and enforces `MAX_QUOTE_SYMBOLS`.
- [x] 3.3 Implement the quote service using enabled PostgreSQL registry mappings as the only runtime mapping source.
- [x] 3.4 Implement cache-hit, refresh, fresh-cache fallback, stale-cache rejection, and per-symbol provider failure behavior.
- [x] 3.5 Add async unit tests for ordering, deduplication, unsupported symbols, persisted mappings, cache TTL, stale threshold, partial outcomes, and concurrent refresh coalescing.

## 4. Quotes HTTP API

- [x] 4.1 Add `GET /v1/quotes` request and camelCase response DTOs with decimal-string serialization and nullable `volume` and `providerTime`.
- [x] 4.2 Add stable request-level `400 INVALID_SYMBOLS` and `400 TOO_MANY_SYMBOLS` responses.
- [x] 4.3 Return HTTP `200` with ordered `quotes` and `errors` arrays for all well-formed symbol-level outcomes.
- [x] 4.4 Preserve request-level `503 DATABASE_UNAVAILABLE` behavior and ensure database or provider internals are not exposed.
- [x] 4.5 Register only the quotes router and required handlers; do not add candle, WebSocket, or other market-data routes.
- [x] 4.6 Add route tests for successful quotes, all-error and partial responses, malformed input, database failure, DTO timestamps, and decimal serialization.

## 5. Integration, Documentation, and Verification

- [x] 5.1 Add a PostgreSQL-gated integration test proving registry rows drive canonical-to-provider quote mapping with mocked Binance HTTP.
- [x] 5.2 Update `docs/spec.md`, `docs/system-design.md`, and `README.md` with the implemented quote flow, exact request errors, configuration, and local request example.
- [x] 5.3 Run Ruff format/check, mypy, unit tests, and the PostgreSQL integration suite when `TEST_DATABASE_URL` is available.
- [x] 5.4 Run Alembic head verification and smoke-test `/health`, `/v1/symbols`, and `/v1/quotes` without adding a database migration.
