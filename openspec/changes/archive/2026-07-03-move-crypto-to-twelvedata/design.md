## Context

The registry currently seeds `BTC/USD` and `ETH/USD` as `BINANCE_SPOT:BTCUSD` and
`BINANCE_SPOT:ETHUSD`. Those Binance Spot symbols exist, but their historical monthly coverage is
shorter than the gateway needs. Twelve Data already backs the broader catalog and uses canonical
slash symbols for many assets, so the smallest useful change is to move the two existing crypto
registry rows to `TWELVE_DATA` while keeping Binance code available for any future Binance-backed
symbols.

## Goals / Non-Goals

**Goals:**

- Make `BTC/USD` and `ETH/USD` resolve to `TWELVE_DATA:BTC/USD` and `TWELVE_DATA:ETH/USD`.
- Keep public quote, candle, stream, and symbol response shapes unchanged.
- Keep existing provider routing by persisted registry mapping.
- Preserve existing database schema.
- Give operators a direct database update for already-deployed databases.

**Non-Goals:**

- No multi-provider fallback.
- No provider priority table.
- No deletion or migration of old Binance candle history.
- No new public symbols such as `BTC/USDT`.

## Decisions

### Update the existing rows in place

Use an Alembic migration to update the two existing canonical rows rather than adding duplicate
symbols or changing the schema.

Existing deployments need the equivalent data update:

```sql
UPDATE supported_symbols
SET provider = 'TWELVE_DATA',
    provider_symbol = symbol,
    enabled = true,
    updated_at = now()
WHERE symbol IN ('BTC/USD', 'ETH/USD');
```

This preserves canonical symbol identity. Existing Binance candle rows remain in
`market_data_candles` under `(BINANCE_SPOT, BTCUSD|ETHUSD, timeframe, open_time)` and are no
longer reused once the registry points at Twelve Data. They can be left alone; cleanup is optional
storage maintenance, not required for correctness.

Alternative considered: add `BTC/USDT` and `ETH/USDT`. Rejected because clients already use
`BTC/USD` and `ETH/USD`, and the request is to move those assets.

### Extend the Twelve Data allowlist

Add `BTC/USD` and `ETH/USD` to the existing Twelve Data supported-provider-symbol set. The current
Twelve Data REST and stream adapters already route by `provider_symbol`, normalize prices, normalize
time-series rows, and derive stream candles from price ticks.

Alternative considered: remove the allowlist. Rejected because the current allowlist protects
against accidental provider calls for unsupported catalog rows.

### Keep Binance provider implementation

Leave Binance quote, candle, and stream adapters registered. This change only changes the default
registry rows for the two canonical crypto symbols.

Alternative considered: remove Binance code. Rejected because the user explicitly wants to keep
the provider and deletion would be unrelated churn.

## Risks / Trade-offs

- Twelve Data now serves two high-traffic crypto symbols -> Mitigation: implement alongside or
  after Twelve Data key rotation, and keep provider failures isolated by existing routing.
- Stream candles from Twelve Data are tick-derived and may use zero volume -> Mitigation: keep the
  current provider-agnostic public shape and document provider-specific volume behavior.
- Existing Binance persisted candles become cold data -> Mitigation: leave them untouched; delete
  later only if storage pressure matters.
- Missing Twelve Data API keys now affect `BTC/USD` and `ETH/USD` -> Mitigation: existing
  sanitized `PROVIDER_UNAVAILABLE` behavior applies; deployments must configure Twelve Data keys.

## Migration Plan

1. Add an Alembic data migration that updates `supported_symbols` for `BTC/USD` and `ETH/USD`.
2. Extend Twelve Data REST and stream allowlists.
3. Update docs and tests that assert the old Binance mapping.
4. Deploy after `TWELVEDATA_API_KEYS` is configured.
5. Rollback by updating the two rows back to `BINANCE_SPOT:BTCUSD` and `BINANCE_SPOT:ETHUSD`.

Rollback SQL:

```sql
UPDATE supported_symbols
SET provider = 'BINANCE_SPOT',
    provider_symbol = CASE symbol
        WHEN 'BTC/USD' THEN 'BTCUSD'
        WHEN 'ETH/USD' THEN 'ETHUSD'
    END,
    enabled = true,
    updated_at = now()
WHERE symbol IN ('BTC/USD', 'ETH/USD');
```
