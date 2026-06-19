## Context

The completed latest-quotes implementation uses an async HTTPX client to call Binance
`/api/v3/ticker/price` directly. It owns query encoding, HTTP status handling, JSON decoding, and
provider-specific test transport. The repository has since adopted an SDK-first provider rule.

The official `binance-sdk-spot` package version `9.2.0`, released June 9, 2026, supports Python
3.14 and exposes `Spot.rest_api.ticker_price(symbols=[...])`. Its REST implementation is
synchronous and uses `requests.Session`; configuration timeout and backoff values are
milliseconds, and retries default to three. The gateway remains async-first and currently intends
one upstream attempt before cache fallback.

## Goals / Non-Goals

**Goals:**

- Replace the custom Binance REST transport with the locked official Spot SDK.
- Preserve the async provider protocol and all existing quote behavior.
- Keep SDK models, exceptions, and sync execution inside `app/providers/`.
- Remove every production HTTPX component made obsolete by the SDK.
- Leave a provider foundation that can reuse the same official SDK for later Spot capabilities.

**Non-Goals:**

- Change `/v1/quotes`, cache, registry, freshness, or error contracts.
- Add candles, authenticated Binance APIs, WebSocket APIs, or WebSocket streams.
- Enable SDK retries or introduce a general provider retry policy.
- Change database schema or seed data.

## Decisions

### Lock the official Spot SDK at 9.2.0

Add `binance-sdk-spot==9.2.0` as a runtime dependency. Move `httpx==0.28.1` back to the development
group because ASGI route tests still require it, while production code no longer does.

Alternative considered: retain direct HTTPX for the single quote endpoint and defer SDK adoption.
Rejected because upcoming Binance features would increase the amount of custom transport and
error code that later needs migration.

### Keep an adapter-owned narrow SDK boundary

`BinanceSpotQuoteProvider` continues implementing the repository-owned async `QuoteProvider`
protocol. It receives a narrow injectable SDK REST client or callable exposing only
`ticker_price(symbols=...)`. A provider factory constructs the official `Spot` client using
`ConfigurationRestAPI`.

SDK response and exception types MUST NOT appear in domain, service, cache, or API modules.
`ProviderQuoteBatch` and `ProviderUnavailableError` remain the stable internal contract.

Alternative considered: inject `Spot` directly into routes and services. Rejected because it
couples business logic and tests to generated SDK APIs.

### Offload synchronous REST calls from the event loop

The adapter invokes the SDK REST operation with `asyncio.to_thread()`. Adapter access is
serialized with an async lock because the SDK owns a shared `requests.Session` and does not
document concurrent thread safety. This is acceptable for the two-symbol MVP and matches the
existing service-level refresh coalescing.

Alternative considered: call the SDK directly from the async method. Rejected because it blocks
the ASGI event loop. Creating a new SDK client per request was rejected because it discards
connection reuse and complicates future provider capabilities.

### Preserve existing timeout and retry semantics

The factory converts `PROVIDER_HTTP_TIMEOUT_SECONDS` to a positive integer number of
milliseconds and supplies it as `ConfigurationRestAPI.timeout`. It sets `retries=0`, preserving
the current one-attempt behavior and allowing the quote cache to remain the fallback mechanism.
`BINANCE_REST_BASE_URL` remains the SDK `base_path`.

No API credentials are configured because the quote endpoint is public.

### Normalize SDK responses defensively

The adapter calls `response.data()` and extracts the generated ticker-price entries without
passing generated models beyond the adapter. It continues validating requested membership,
uniqueness, missing symbols, and finite positive decimal prices. Unexpected response shape is a
provider failure or per-symbol unavailability according to the existing quote contract.

The implementation maps the SDK base `binance_common.errors.Error`, response decoding failures,
and unexpected SDK failures to `ProviderUnavailableError` without exposing details. Cancellation
from the async caller is not converted.

### Delete superseded transport code instead of retaining fallback paths

After SDK tests pass:

- delete `app/core/http.py`;
- remove HTTPX lifespan setup and `app.state.http_client`;
- remove HTTP client dependency injection from the quote route;
- remove `_encode_symbols`, direct URL construction, raw HTTP status handling, and HTTPX
  exceptions from the Binance adapter;
- replace HTTPX `MockTransport` provider and integration fixtures with fake SDK/provider
  boundaries;
- remove production documentation that describes HTTPX as the Binance runtime client.

There will be no direct-HTTP fallback path. Rollback uses the previous application revision.

## Risks / Trade-offs

- [Synchronous SDK blocks worker threads] -> Use `asyncio.to_thread`, retain the upstream timeout,
  and serialize SDK session access.
- [Generated response models change in an SDK upgrade] -> Pin `9.2.0`, isolate model access in one
  adapter, and require adapter contract tests before upgrades.
- [SDK default retries change latency and quota use] -> Explicitly set `retries=0`.
- [SDK exception hierarchy changes] -> Catch the documented SDK base error and keep an
  unexpected-exception safety boundary with sanitized output.
- [SDK exposes no public REST close method] -> Keep one process-lifetime client, avoid private
  session access, and revisit lifecycle handling when Binance adds a supported close API.
- [Serialization limits provider concurrency] -> Accept for the two-symbol MVP; introduce an
  owned executor/client pool only after measured demand.

## Migration Plan

1. Add and lock `binance-sdk-spot==9.2.0`; inspect installed response models and type information.
2. Add SDK client construction and adapter contract tests before removing the HTTPX path.
3. Switch route wiring to the SDK adapter and run the full regression suite.
4. Delete all superseded production and test transport code.
5. Update stack and provider documentation and perform a live Binance quote smoke test.
6. Roll back by deploying the prior revision; no database rollback is required.

## Open Questions

None for this migration. WebSocket SDK lifecycle and connection pooling belong to their future
capability changes.
