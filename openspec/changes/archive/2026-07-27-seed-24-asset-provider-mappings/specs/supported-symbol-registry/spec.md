## ADDED Requirements

### Requirement: Approved provider mappings are seeded for the 24-asset catalog

The database SHALL seed the approved 24 canonical assets with one active default provider mapping
per asset and SHALL seed only the five approved inactive yfinance alternatives. The seed SHALL
contain no provider fallback, route-specific selection, priority, or gold-futures proxy.

#### Scenario: Twelve Data defaults are seeded

- **WHEN** the provider-mapping seed is applied
- **THEN** `AAPL`, `BTC/USD`, `EUR/USD`, `QQQ`, and `XAU/USD` have active `TWELVE_DATA` mappings
  using provider symbols `AAPL`, `BTC/USD`, `EUR/USD`, `QQQ`, and `XAU/USD` respectively

#### Scenario: Binance default is seeded

- **WHEN** the provider-mapping seed is applied
- **THEN** `ETH/USD` has active mapping `BINANCE_SPOT:ETHUSD`

#### Scenario: yfinance defaults are seeded

- **WHEN** the provider-mapping seed is applied
- **THEN** the active yfinance mappings are `AUD/USD:AUDUSD=X`, `BRENT:BZ=F`, `COFFEE:KC=F`,
  `CORN:ZC=F`, `DJI:^DJI`, `GBP/USD:GBPUSD=X`, `MSFT:MSFT`, `NATGAS:NG=F`, `NDX:^NDX`,
  `NVDA:NVDA`, `SPX:^GSPC`, `SPY:SPY`, `SUGAR:SB=F`, `TSLA:TSLA`, `USD/JPY:JPY=X`,
  `WHEAT:ZW=F`, `WTI:CL=F`, and `XAG/USD:SI=F`

#### Scenario: Approved alternatives are seeded

- **WHEN** the provider-mapping seed is applied
- **THEN** inactive mappings exist for `AAPL:YFINANCE:AAPL`, `BTC/USD:YFINANCE:BTC-USD`,
  `ETH/USD:YFINANCE:ETH-USD`, `EUR/USD:YFINANCE:EURUSD=X`, and
  `QQQ:YFINANCE:QQQ`
- **AND** no other inactive mapping is introduced by this seed

#### Scenario: XAU has no yfinance proxy

- **WHEN** mappings for `XAU/USD` are inspected
- **THEN** `TWELVE_DATA:XAU/USD` is its only seeded mapping
- **AND** neither `GC=F` nor another yfinance provider symbol is seeded for `XAU/USD`

#### Scenario: Fresh catalog is seeded

- **WHEN** the migration is applied to the current 24-asset catalog without custom mappings
- **THEN** `symbol_provider_mappings` contains 29 seeded mappings
- **AND** exactly 24 mappings are active
- **AND** every canonical asset has exactly one active mapping

#### Scenario: Legacy provider columns remain compatible

- **WHEN** the migration selects each active default
- **THEN** `supported_symbols.provider` and `supported_symbols.provider_symbol` match that active
  mapping
- **AND** the current runtime routes quote, candle, and stream requests through the same provider

#### Scenario: Existing custom mapping is present

- **WHEN** the migration encounters a mapping not owned by the known historical seed or this seed
- **THEN** it preserves that mapping row
- **AND** the approved default remains the asset's only active mapping

#### Scenario: Seed operation is repeated

- **WHEN** the seed reconciliation is applied more than once
- **THEN** it produces the same approved mappings and active selections without duplicates

