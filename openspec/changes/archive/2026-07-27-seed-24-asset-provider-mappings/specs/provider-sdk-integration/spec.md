## MODIFIED Requirements

### Requirement: yfinance latest quotes use the repository-owned adapter

The gateway SHALL obtain yfinance latest prices through a repository-owned provider adapter using
the locked yfinance package and SHALL keep all yfinance types, sessions, payloads, and exceptions
inside `app/providers/`.

#### Scenario: Supported yfinance quote is requested

- **WHEN** the adapter receives one of `AAPL`, `AUDUSD=X`, `BZ=F`, `BTC-USD`, `KC=F`, `ZC=F`,
  `^DJI`, `ETH-USD`, `EURUSD=X`, `GBPUSD=X`, `MSFT`, `NG=F`, `^NDX`, `NVDA`, `QQQ`, `^GSPC`,
  `SPY`, `SB=F`, `TSLA`, `JPY=X`, `ZW=F`, `CL=F`, or `SI=F`
- **THEN** it calls `Ticker.get_info()` for that provider symbol
- **AND** it uses `regularMarketPrice` as the provider price candidate

#### Scenario: Provider symbol is outside the yfinance allowlist

- **WHEN** the adapter receives a provider symbol outside the 23 approved mappings
- **THEN** it marks that symbol unavailable
- **AND** it makes no yfinance request for that symbol

#### Scenario: yfinance boundary is inspected

- **WHEN** production modules outside `app/providers/` are analyzed
- **THEN** they contain no imports of yfinance modules, clients, sessions, payload models, or
  exceptions

## ADDED Requirements

### Requirement: Approved yfinance symbols are shared across market-data adapters

The gateway MUST apply the same 23-symbol yfinance allowlist to latest-quote, historical-candle,
and WebSocket stream operations.

#### Scenario: Approved mapping is routed through any market-data path

- **WHEN** an approved yfinance mapping is active and requested through quote, candle, or stream
- **THEN** the matching yfinance adapter accepts its persisted provider symbol
- **AND** no adapter performs provider-symbol remapping or cross-provider fallback

#### Scenario: Unapproved mapping is requested through any market-data path

- **WHEN** a yfinance provider symbol outside the approved set reaches quote, candle, or stream
- **THEN** the matching adapter rejects it through the sanitized provider-unavailable boundary
- **AND** it makes no upstream request or subscription for that symbol

