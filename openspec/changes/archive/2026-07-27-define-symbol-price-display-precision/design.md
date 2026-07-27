## Context

The gateway stores exact market values as `Decimal` and serializes them in fixed-point notation.
The shared serializer intentionally preserves the normalized value's scale, so provider values can
contain more fractional digits than the product wants to show. The supported-symbol registry is
already the database-backed source of truth for per-symbol metadata and is exposed through
`GET /v1/symbols`.

The current enabled catalog contains 24 symbols across crypto, Forex, commodities, US stocks,
ETFs, and stock indexes. Display precision is a product convention, not provider precision,
instrument tick size, or a storage constraint.

## Goals / Non-Goals

**Goals:**

- Define one explicit number of price display decimals for every enabled symbol.
- Make the metadata available to every HTTP or WebSocket consumer through the symbol endpoint.
- Reject missing or invalid display precision for future registry records.
- Preserve all existing market-data values and public quote/candle event shapes.

**Non-Goals:**

- Rounding, padding, or otherwise quantizing market values inside the gateway.
- Defining order precision, tick size, lot size, volume precision, currency units, or locale.
- Repeating static display metadata in quote, candle, historical-price, or WebSocket payloads.
- Adding a new dependency or a runtime provider-metadata lookup.

## Decisions

### Store display precision in the symbol registry

Add a required `price_display_decimals` small integer to `supported_symbols`, map it through
`SupportedSymbol`, and expose it as `priceDisplayDecimals` from `GET /v1/symbols`.

This keeps mutable per-symbol policy beside the existing symbol metadata. A hard-coded formatter
map was rejected because it would duplicate the database catalog and drift when symbols change.
Inferring the value from `asset_class` was rejected because symbols within `FOREX` and
`COMMODITY` require different display decimals.

### Require explicit valid values

The database column will be `NOT NULL` with a check constraint from 0 through 18 inclusive and no
server default. Existing rows will be backfilled before the constraint becomes mandatory. A
default of 2 was rejected because it would silently give future FX or commodity symbols incorrect
metadata.

### Seed the agreed catalog values

| Display decimals | Symbols |
| --- | --- |
| 5 | `AUD/USD`, `EUR/USD`, `GBP/USD` |
| 3 | `USD/JPY`, `XAG/USD`, `NATGAS` |
| 2 | `BTC/USD`, `ETH/USD`, `XAU/USD`, `WTI`, `BRENT`, `COFFEE`, `SUGAR`, `WHEAT`, `CORN`, `AAPL`, `TSLA`, `NVDA`, `MSFT`, `SPY`, `QQQ`, `SPX`, `NDX`, `DJI` |

The values define fixed fractional digits for presentation. Consumers round and pad when
rendering, for example raw `XAU/USD` value `2934.5678` displays as `2934.57`.

### Keep transport and persistence values unchanged

Provider adapters, domain quote/candle values, caches, candle persistence, decimal serialization,
latest quotes, historical prices, historical candles, and WebSocket events continue using the
normalized `Decimal` value without applying `price_display_decimals`.

Consumers load `/v1/symbols`, build a `symbol -> priceDisplayDecimals` map, and apply it only at
render time. A consumer that lacks metadata should show the raw decimal string rather than infer a
value from asset class.

Adding `priceDisplayDecimals` to every market-data payload was rejected because the metadata is
static, would duplicate data on high-frequency streams, and would change exact public event
shapes.

## Risks / Trade-offs

- [Consumers do not load symbol metadata] → Keep raw decimal strings valid and document raw display
  as the fallback.
- [A downstream client rejects additive JSON fields] → Treat the `/v1/symbols` contract update as
  an explicit release item and update strict client schemas before adoption.
- [Product display convention changes] → Update the registry value without changing stored market
  data or provider adapters.
- [Display precision is mistaken for tick size] → Document that the field controls presentation
  only and cannot validate orders or market increments.
- [Application deploys before its migration] → Deploy the schema migration before the application
  version that selects the new column.

## Migration Plan

1. Add `price_display_decimals` as nullable.
2. Backfill all 24 existing symbols with the agreed values.
3. Abort the migration if any enabled registry row remains null.
4. Set the column `NOT NULL` and add the inclusive 0-to-18 check constraint.
5. Deploy the application model, repository mapping, and additive `/v1/symbols` field.
6. Deploy downstream formatting consumers after they accept the new symbol response.

Rollback the application first. The extra database column is safe for the previous application;
drop it only after the old application version is restored.

## Open Questions

None. The catalog values and metadata-only boundary were approved during exploration.
