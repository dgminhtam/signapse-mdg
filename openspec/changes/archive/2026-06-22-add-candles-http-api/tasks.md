## 1. Candle Contract and Domain

- [x] 1.1 Add typed candle and provider-batch domain models plus repository and provider protocols
- [x] 1.2 Add the explicit `1m`, `5m`, `15m`, `1h`, and `1d` timeframe registry with duration and provider mappings
- [x] 1.3 Add candle request errors and stable messages for unsupported symbols, unsupported timeframes, invalid ranges, provider failures, and database failures
- [x] 1.4 Add unit tests for timeframe lookup, UTC boundary alignment, half-open range semantics, range-day limits, and expected-candle-count limits

## 2. Configuration and Persistence

- [x] 2.1 Add typed `MAX_CANDLE_RANGE_DAYS` and `MAX_CANDLES_PER_REQUEST` settings with defaults of 30 and 1,000
- [x] 2.2 Add the `market_data_candles` SQLAlchemy model with exact numeric OHLCV columns, completion state, uniqueness, and lookup indexes
- [x] 2.3 Add an Alembic migration that creates and cleanly downgrades the candle table, unique constraint, and indexes
- [x] 2.4 Expose an async session-factory dependency suitable for operation-scoped candle repository transactions
- [x] 2.5 Implement operation-scoped registry lookup and candle range query methods that release the read session before provider I/O
- [x] 2.6 Implement transactional idempotent upsert of complete candles and map SQLAlchemy failures to `DatabaseUnavailableError`
- [x] 2.7 Add PostgreSQL integration tests for migration shape, uniqueness, ordered range queries, idempotent upserts, and rollback

## 3. Binance Kline Adapter

- [x] 3.1 Extend the Binance Spot adapter boundary with the official SDK `klines` operation and internal public-timeframe-to-SDK-enum mapping
- [x] 3.2 Execute synchronous kline calls through `asyncio.to_thread` while preserving serialized shared SDK-client access and cancellation
- [x] 3.3 Convert `[from,to)` to Binance millisecond parameters, including the exclusive end boundary minus one millisecond and an explicit limit
- [x] 3.4 Normalize valid nested kline arrays into `Decimal` and UTC candle models while filtering to the requested range
- [x] 3.5 Reject malformed arrays, invalid or non-finite OHLCV values, inconsistent timestamps, duplicate open times, and out-of-range entries through `ProviderUnavailableError`
- [x] 3.6 Add adapter tests for SDK arguments, normalization, malformed payloads, SDK errors, event-loop progress, serialized calls, and cancellation

## 4. Candle Service

- [x] 4.1 Implement canonical symbol resolution through the enabled PostgreSQL registry without exposing internal mapping fields
- [x] 4.2 Implement repository-first retrieval and contiguous missing-slot detection for an aligned requested range
- [x] 4.3 Fetch only missing ranges, merge provider and persisted candles by open time, retain persisted complete candles on overlap, and sort deterministically
- [x] 4.4 Determine completion from provider close time and gateway receive time, then persist only complete fetched candles
- [x] 4.5 Ensure a full database hit skips Binance and a provider-omitted slot is not synthesized
- [x] 4.6 Add service tests for full hits, partial gaps, multiple gaps, overlap precedence, omitted slots, forming candles, and provider/database failures

## 5. HTTP API and Error Handling

- [x] 5.1 Add a contract-aware query parser for `symbol`, `timeframe`, `from`, and `to` that returns gateway `400` errors instead of FastAPI `422` responses
- [x] 5.2 Add `GET /v1/candles` dependency wiring and register its router and exception handlers in the app factory
- [x] 5.3 Add strict response DTOs containing only `symbol`, `timeframe`, `from`, `to`, and normalized candle fields
- [x] 5.4 Verify `assetClass`, `provider`, and `providerSymbol` cannot leak through response-model serialization
- [x] 5.5 Generalize the sanitized `DATABASE_UNAVAILABLE` response message so it covers both registry and candle persistence
- [x] 5.6 Add route tests for successful and empty responses, exact field sets, decimal/UTC serialization, every validation error, unsupported registry values, and sanitized `503` failures

## 6. End-to-End Integration

- [x] 6.1 Add an integration test proving a cold request uses the persisted provider mapping, fetches Binance-normalized candles, and stores only closed candles
- [x] 6.2 Add an integration test proving a repeated request is served from PostgreSQL without another provider call
- [x] 6.3 Add an integration test proving a partially persisted range fetches and upserts only the missing section
- [x] 6.4 Add an integration test proving database read sessions are closed before a gated provider call waits

## 7. Documentation and Verification

- [x] 7.1 Update `docs/spec.md` and `docs/system-design.md` with the minimal provider-agnostic response and finalized range/count semantics
- [x] 7.2 Update `.env.example` and `README.md` with candle settings, migration guidance, endpoint usage, and response example
- [x] 7.3 Run `uv run ruff format .` and `uv run ruff check .`
- [x] 7.4 Run `uv run mypy app`
- [x] 7.5 Run `uv run pytest`, including PostgreSQL integration tests when `TEST_DATABASE_URL` is configured
