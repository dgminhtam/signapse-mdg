## 1. Dependency and Configuration

- [x] 1.1 Add the official `twelvedata` SDK dependency and refresh the lockfile.
- [x] 1.2 Add typed Twelve Data settings for API key, REST base URL, and provider timeout usage.
- [x] 1.3 Document Twelve Data environment placeholders in `.env.example` without committing credentials.

## 2. Twelve Data Provider Foundation

- [x] 2.1 Add a Twelve Data Forex provider module under `app/providers/` that owns all SDK imports.
- [x] 2.2 Add provider-symbol validation/discovery support for `EUR/USD`, `GBP/USD`, `USD/JPY`, and `AUD/USD`.
- [x] 2.3 Add latest-price normalization that converts Twelve Data SDK output into `Decimal` values keyed by provider symbol.
- [x] 2.4 Add time-series normalization for supported gateway timeframe mappings without wiring public candle routes.
- [x] 2.5 Execute synchronous SDK REST calls outside the event loop and serialize shared SDK client access.
- [x] 2.6 Map Twelve Data SDK/provider failures to the existing sanitized provider-unavailable boundary.
- [x] 2.7 Ensure no Twelve Data SDK imports appear outside `app/providers/`.

## 3. Forex Registry Seed

- [x] 3.1 Add an Alembic migration that idempotently seeds `EUR/USD`, `GBP/USD`, `USD/JPY`, and `AUD/USD` as enabled `FOREX` symbols mapped to `TWELVE_DATA`.
- [x] 3.2 Ensure the Forex seed migration preserves existing `BTC/USD` and `ETH/USD` Binance mappings.
- [x] 3.3 Add downgrade behavior that removes only the seeded Twelve Data Forex mappings when safe.

## 4. Tests and Documentation

- [x] 4.1 Add provider unit tests using fake SDK/client boundaries for price normalization, candle normalization, invalid payloads, and provider errors.
- [x] 4.2 Add async-boundary tests proving Twelve Data SDK REST work is offloaded and serialized.
- [x] 4.3 Add registry migration/integration tests covering the Forex seed and idempotent reseeding.
- [x] 4.4 Update provider/tech-stack documentation to describe Twelve Data as the selected low-cost Forex REST foundation.
- [x] 4.5 Confirm existing public quote, candle, and WebSocket tests still exercise Binance-backed behavior only.

## 5. Verification

- [x] 5.1 Run `openspec validate integrate-twelvedata-forex-foundation --strict`.
- [x] 5.2 Run the relevant provider, registry, and existing market-data test suites.
- [x] 5.3 Run `ruff` and `mypy` for touched application code.
