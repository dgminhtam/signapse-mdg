## ADDED Requirements

### Requirement: yfinance planned catalog symbols are seeded

The database SHALL seed enabled mappings for the planned catalog assets that do not already have a
provider, using `YFINANCE` as the provider identifier.

#### Scenario: yfinance seed is applied

- **WHEN** the yfinance seed migration is applied
- **THEN** `XAG/USD` is enabled as `COMMODITY` mapped to `YFINANCE:SI=F`
- **AND** `BRENT` is enabled as `COMMODITY` mapped to `YFINANCE:BZ=F`
- **AND** `NATGAS` is enabled as `COMMODITY` mapped to `YFINANCE:NG=F`
- **AND** `COFFEE` is enabled as `COMMODITY` mapped to `YFINANCE:KC=F`
- **AND** `SUGAR` is enabled as `COMMODITY` mapped to `YFINANCE:SB=F`
- **AND** `WHEAT` is enabled as `COMMODITY` mapped to `YFINANCE:ZW=F`
- **AND** `CORN` is enabled as `COMMODITY` mapped to `YFINANCE:ZC=F`
- **AND** `SPX` is enabled as `STOCK_INDEX` mapped to `YFINANCE:^GSPC`
- **AND** `NDX` is enabled as `STOCK_INDEX` mapped to `YFINANCE:^NDX`
- **AND** `DJI` is enabled as `STOCK_INDEX` mapped to `YFINANCE:^DJI`

#### Scenario: yfinance seed is repeated

- **WHEN** any required yfinance canonical symbol already exists
- **THEN** the migration restores its required asset class, provider, provider symbol, and enabled
  value without creating duplicate registry records

#### Scenario: Existing provider mappings are preserved

- **WHEN** the yfinance seed migration is applied
- **THEN** existing `BINANCE_SPOT` and `TWELVE_DATA` registry mappings remain enabled and unchanged

### Requirement: STOCK_INDEX is a public registry asset class

The supported-symbol API SHALL expose `STOCK_INDEX` for enabled stock-index registry records.

#### Scenario: Seeded stock indexes are listed

- **WHEN** a client sends `GET /v1/symbols` after the yfinance seed migration is applied
- **THEN** `SPX`, `NDX`, and `DJI` can be returned with asset class `STOCK_INDEX`
- **AND** the response uses the existing supported-symbol response shape

### Requirement: yfinance registry seeding does not enable market-data APIs

Seeding yfinance symbols SHALL NOT change public quote, candle, or WebSocket market-data routing in
this change.

#### Scenario: Market-data request targets a yfinance-seeded symbol

- **WHEN** a client requests quote, candle, or stream data for an enabled `YFINANCE` symbol
- **THEN** the gateway makes no yfinance upstream request
- **AND** no yfinance adapter is required to serve the request in this change
