## MODIFIED Requirements

### Requirement: Quote requests use enabled registry mappings

The gateway MUST validate canonical symbols and obtain provider mappings by joining enabled
PostgreSQL registry records to their single active normalized mapping. It MUST NOT use a hard-coded
runtime mapping, a legacy provider column, or an inactive mapping.

#### Scenario: Enabled crypto symbols are requested

- **WHEN** a client requests `BTC/USD,ETH/USD` and both registry records are enabled
- **THEN** the gateway resolves their provider symbols from their active mappings
- **AND** it refreshes each symbol through the provider selected by that active mapping

#### Scenario: Enabled Forex symbols are requested

- **WHEN** a client requests `EUR/USD,GBP/USD,USD/JPY,AUD/USD,XAU/USD,AAPL,TSLA,NVDA,MSFT` and
  those registry records are enabled
- **THEN** the gateway resolves every provider and provider symbol from its active mapping
- **AND** it groups refreshes by those resolved providers

#### Scenario: Unknown or disabled symbol is requested

- **WHEN** a well-formed request contains a canonical symbol that has no enabled registry record
- **THEN** the response includes an `UNSUPPORTED_SYMBOL` error for that symbol
- **AND** other requested symbols continue to be processed

#### Scenario: Active provider mapping changes

- **WHEN** an enabled symbol's active provider mapping is changed in PostgreSQL
- **THEN** a subsequent quote refresh uses the newly active provider and provider symbol
- **AND** it does not fall back to the previous or another inactive mapping

#### Scenario: Enabled symbol lacks an active mapping

- **WHEN** an enabled requested symbol has no active normalized mapping
- **THEN** the gateway responds with HTTP status `503`
- **AND** the request-level error code is `DATABASE_UNAVAILABLE`
- **AND** no provider quote request is made

#### Scenario: Registry is unavailable

- **WHEN** the gateway cannot query the symbol registry for a quote request
- **THEN** it responds with HTTP status `503`
- **AND** the request-level error code is `DATABASE_UNAVAILABLE`
- **AND** no provider quote request is made
