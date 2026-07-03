## Context

The symbol registry contains ten enabled `YFINANCE` mappings, but the quote provider router has no
yfinance adapter and therefore reports those symbols as unavailable. The public quote service
already owns registry lookup, cache coalescing, TTL and stale fallback behavior, request ordering,
provider grouping, and stable per-symbol errors.

yfinance 1.4.1 is synchronous and wraps unofficial Yahoo Finance endpoints. Research against the
installed package and live smoke tests on June 23, 2026 showed:

- `Ticker.get_info()["regularMarketPrice"]` returned prices for all ten seeded symbols.
- Sequential `get_info()` calls for all ten symbols completed in about 4.2 seconds while reusing
  Yahoo session state.
- `download(period="1d", interval="1m")` returned no data for all seven futures mappings.
- `download(period="5d", interval="1m")` returned all symbols but fetched thousands of rows and was
  too slow for the quote path.
- `fast_info.last_price` derives its value from historical price downloads and is not a lighter
  quote primitive.

yfinance internally uses a process-wide `YfData` singleton whose session and cookie state are
mutable. The adapter must therefore avoid concurrent mutation of different sessions and must keep
all SDK types and exceptions inside `app/providers/`.

## Goals / Non-Goals

**Goals:**

- Serve all ten seeded `YFINANCE` symbols through the existing `/v1/quotes` contract.
- Normalize `regularMarketPrice` into finite positive `Decimal` values keyed by provider symbol.
- Keep synchronous SDK work off the event loop and bound each underlying HTTP request with the
  existing provider timeout setting.
- Preserve partial success when one Yahoo symbol is missing, invalid, rate-limited, or otherwise
  unavailable.
- Reuse the existing quote cache, stale fallback, provider grouping, and sanitized error behavior.

**Non-Goals:**

- Do not add yfinance historical candle routing.
- Do not add yfinance WebSocket or polling-based streaming.
- Do not expose provider timestamps, market state, quote type, currency, units, or futures roll
  metadata in the public quote response.
- Do not replace existing Binance or Twelve Data mappings with yfinance alternatives.
- Do not change the seeded provider symbols or rename the `XAG/USD` futures proxy.
- Do not treat yfinance as an official Yahoo SDK or make claims beyond Yahoo's available data.

## Decisions

### Use `Ticker.get_info()` and `regularMarketPrice`

For each requested allowlisted provider symbol, the adapter will construct a yfinance `Ticker`,
call `get_info()`, and read `regularMarketPrice`. A missing field, boolean, non-numeric value,
non-finite value, or value less than or equal to zero marks only that provider symbol unavailable.

`Decimal(str(value))` will be used so Python binary floating-point artifacts are not introduced by
constructing `Decimal` directly from a float.

Alternatives considered:

- `download()` was rejected because the lightweight one-day query did not cover the futures
  mappings and the five-day fallback was too expensive for latest quotes.
- `fast_info.last_price` was rejected because it loads historical data and does not provide a
  simpler latest-quote path.
- Calling Yahoo endpoints directly was rejected because the repository already selected yfinance
  as the provider boundary and direct private protocol integration would duplicate its cookie,
  crumb, and transport behavior.

### Allowlist only the ten seeded provider symbols

The adapter will own an explicit allowlist containing `SI=F`, `BZ=F`, `NG=F`, `KC=F`, `SB=F`,
`ZW=F`, `ZC=F`, `^GSPC`, `^NDX`, and `^DJI`. Symbols outside this set will be marked unavailable
without making an upstream request.

This prevents the runtime adapter from silently becoming a generic Yahoo proxy and keeps coverage
aligned with the persisted catalog approved in the preceding change.

### Run one serialized batch in a worker thread

`fetch_latest_prices()` will acquire an adapter lock and use `asyncio.to_thread()` to execute the
synchronous batch. The worker will process supported symbols sequentially while reusing one
yfinance-compatible HTTP session.

The serialized design matches the existing shared-client adapter pattern and avoids races in
yfinance's process-wide `YfData` singleton, mutable session, cookie, and crumb state. Cache refresh
coalescing and the adapter lock also prevent overlapping yfinance batches.

Alternative considered: parallel `get_info()` calls reduced observed latency, but yfinance does not
document thread-safe concurrent mutation of its singleton session. Correctness and predictable
rate behavior take priority for this first quote integration.

### Clamp yfinance transport timeout through its session boundary

`get_info()` does not expose a timeout argument and yfinance defaults internal requests to a longer
timeout. The adapter will create a supported yfinance session whose request method replaces or
clamps supplied timeout values to `PROVIDER_HTTP_TIMEOUT_SECONDS`, then pass that same session to
each `Ticker`.

The adapter will not rely solely on cancelling `asyncio.to_thread()`, because cancellation cannot
stop an already-running blocking network operation. The transport timeout is the actual bound.

No new yfinance base URL or credential setting is introduced because yfinance owns its Yahoo
endpoint selection and the selected data does not require an API key.

### Isolate symbol failures inside the yfinance batch

Expected yfinance, HTTP, timeout, rate-limit, payload, and conversion failures for one ticker will
mark that ticker unavailable and allow remaining tickers to continue. Failure to create or use the
shared provider session, or another batch-level failure that prevents all work, will cross the
adapter boundary as `ProviderUnavailableError`.

The adapter will not log raw quote payloads, cookies, provider URLs containing transient state, or
exception text into public responses. Async cancellation will continue to propagate.

### Wire yfinance only into the quote dependency graph

The quote route factory will construct a cached yfinance provider using
`PROVIDER_HTTP_TIMEOUT_SECONDS` and register it under `YFINANCE`. No credential gate is needed.
Candle and stream provider routers will retain their current unavailable behavior for
`YFINANCE`.

The public response remains exactly `symbol`, `price`, and `receivedAt`; the gateway receive time
continues to drive cache TTL and freshness calculations.

## Risks / Trade-offs

- Yahoo or yfinance can change undocumented response behavior -> Validate payloads defensively,
  isolate failures, and return stable provider-unavailable errors.
- yfinance and Yahoo usage terms may not fit a production commercial deployment -> Keep the
  limitation documented and require product/legal approval before production rollout.
- Sequential fetching can approach the route latency budget when many symbols are cold -> Reuse
  the existing ten-second cache, shared refresh lock, session state, and per-request timeout; gather
  production timing before considering concurrency.
- A provider timeout can occur once per ticker, making a fully failing ten-symbol batch slow ->
  retain partial progress and measure the first deployment; introduce a separate batch deadline
  only if it can safely stop underlying work.
- `regularMarketPrice` can represent the last regular-session value while a market is closed ->
  preserve the current contract, where `receivedAt` is gateway receive time rather than provider
  trade time.
- Futures prices have contract-specific units and rolling-contract semantics -> Keep the proxy
  mapping documented and do not imply spot pricing or expose units absent from the API contract.
- yfinance's singleton state may interact with future candle or stream adapters -> Keep this
  provider serialized until a later design explicitly coordinates all yfinance workloads.

## Migration Plan

1. Add the quote adapter, session timeout boundary, allowlist, and focused unit tests.
2. Register `YFINANCE` in quote dependency wiring and update router/API integration tests.
3. Update documentation from registry-only to quote-enabled status while retaining candle and
   stream limitations.
4. Run unit, integration, lint, type, and strict OpenSpec validation.
5. Deploy without a database migration or new environment variable.
6. Smoke-test individual and mixed-provider quote requests against all ten symbols.

Rollback removes the `YFINANCE` quote provider registration and adapter. Registry rows and the
locked dependency can remain because the pre-change behavior already treats those rows as
provider-unavailable for market-data routes.

## Open Questions

- Production use still requires confirmation that Yahoo Finance and yfinance usage terms are
  acceptable for the gateway's deployment model.
- Operational measurements after the first rollout will determine whether a safe batch deadline or
  limited concurrency is needed.
