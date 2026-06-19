## Why

The Binance quote adapter currently reimplements REST transport, payload decoding, and HTTP error
handling even though Binance provides an official Spot SDK. Migrating now establishes the
repository's SDK-first provider foundation before additional Binance capabilities make the custom
transport more expensive to replace.

## What Changes

- Add and lock the official `binance-sdk-spot` runtime dependency.
- Replace the direct HTTPX Binance quote request with the SDK `ticker_price` operation.
- Preserve the async `QuoteProvider` contract by offloading the synchronous SDK REST call from the
  event loop.
- Configure SDK base URL, timeout, and retry behavior from existing typed settings.
- Normalize SDK response models and exceptions inside the Binance adapter.
- Remove production HTTPX client lifecycle, dependency wiring, raw request encoding, raw JSON
  decoding, and HTTPX-specific provider tests that the SDK supersedes.
- Keep HTTPX as a development dependency for FastAPI route and ASGI integration tests.
- Preserve the existing `/v1/quotes` API, registry mapping, cache, freshness, and per-symbol error
  behavior without a database migration.

## Capabilities

### New Capabilities

- `provider-sdk-integration`: Defines the SDK-first Binance adapter boundary, non-blocking
  execution, normalized errors and models, and removal of superseded direct-transport code.

### Modified Capabilities

None. The external latest-quotes requirements remain unchanged.

## Impact

- Replaces the implementation inside `app/providers/binance_spot.py`.
- Removes `app/core/http.py` and HTTPX application lifespan state when no production caller
  remains.
- Simplifies quote-route dependency wiring to construct or inject the Binance SDK adapter.
- Reworks provider and PostgreSQL mapping tests around a fake SDK boundary.
- Updates `pyproject.toml`, `uv.lock`, provider documentation, and the locked technology stack.
- Introduces a synchronous third-party SDK behind `asyncio.to_thread`, requiring explicit
  concurrency and shutdown tests.
