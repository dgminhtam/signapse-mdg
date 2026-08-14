## MODIFIED Requirements

### Requirement: Quote requests use enabled registry mappings

The gateway MUST validate canonical symbols and resolve one immutable Provider Selection for each enabled symbol from its normalized Provider Mappings. When `provider` is omitted it MUST select the Default Provider; when `provider` is supplied it MUST select the exact matching mapping regardless of default state. It MUST NOT use a hard-coded runtime mapping, a legacy provider column, automatic provider fallback, or a mapping belonging to another symbol.

#### Scenario: Enabled symbols use their defaults

- **WHEN** a client requests enabled symbols without a Provider Override
- **THEN** the gateway resolves every provider and provider symbol from each symbol's Default Provider
- **AND** groups refreshes by those resolved providers

#### Scenario: Request-wide override is supported by some symbols

- **WHEN** a well-formed quote request names one Provider Override
- **AND** some requested symbols have that Provider Mapping while others do not
- **THEN** mapped symbols are refreshed through the selected mapping
- **AND** every unmapped symbol receives a per-symbol `UNSUPPORTED_PROVIDER` error
- **AND** the response has HTTP status `200`
- **AND** no unmapped symbol falls back to its Default Provider

#### Scenario: Request-wide override is supported by every symbol

- **WHEN** every enabled requested symbol has a Provider Mapping matching the Provider Override
- **THEN** the gateway refreshes every symbol through its selected mapping
- **AND** the Provider Override applies to the complete request

#### Scenario: Unknown or disabled symbol is requested

- **WHEN** a well-formed request contains a canonical symbol that has no enabled registry record
- **THEN** the response includes an `UNSUPPORTED_SYMBOL` error for that symbol
- **AND** other requested symbols continue to be processed

#### Scenario: Default Provider changes

- **WHEN** an enabled symbol's Default Provider is changed in PostgreSQL
- **THEN** a subsequent quote request without an override uses the new default mapping
- **AND** a request with an explicit matching override uses its requested mapping

#### Scenario: Enabled symbol lacks a Default Provider

- **WHEN** an enabled requested symbol has no Default Provider
- **THEN** the gateway responds with HTTP status `503`
- **AND** the request-level error code is `DATABASE_UNAVAILABLE`
- **AND** an explicit Provider Override does not bypass the invalid registry state
- **AND** no provider quote request is made

#### Scenario: Registry is unavailable

- **WHEN** the gateway cannot query the symbol registry for a quote request
- **THEN** it responds with HTTP status `503`
- **AND** the request-level error code is `DATABASE_UNAVAILABLE`
- **AND** no provider quote request is made

### Requirement: Quote cache limits provider requests

The gateway SHALL store latest normalized quotes in a process-local cache using configurable TTL and freshness thresholds while keeping cache and freshness metadata internal. Each entry MUST be identified by canonical symbol, Provider Identifier, and provider symbol, and MUST be reused only by a request resolving to that same Provider Mapping.

#### Scenario: Same-selection cache entry is within TTL

- **WHEN** a requested quote resolves to the mapping owning a cached quote
- **AND** the quote's age does not exceed `QUOTE_CACHE_TTL_SECONDS`
- **THEN** the cached quote is returned using the minimal public representation
- **AND** no provider request is made for that symbol

#### Scenario: Different mapping has a fresh cache entry

- **WHEN** a requested quote resolves to one Provider Mapping
- **AND** a fresh cached quote exists only for another mapping of the same canonical symbol
- **THEN** the other mapping's quote is not used
- **AND** the gateway attempts to refresh through the selected mapping

#### Scenario: Same-selection cache entry has exceeded TTL

- **WHEN** a requested quote's same-selection cache entry is older than `QUOTE_CACHE_TTL_SECONDS`
- **THEN** the gateway attempts to refresh that symbol through the selected mapping

#### Scenario: Refresh fails but same-selection cached quote is still fresh

- **WHEN** provider refresh fails and the same-selection cached quote's age does not exceed `QUOTE_STALE_AFTER_SECONDS`
- **THEN** the cached quote is returned using the minimal public representation
- **AND** no public freshness field is added to the quote

#### Scenario: Refresh fails and same-selection cached quote is stale

- **WHEN** provider refresh fails and the same-selection cached quote's age exceeds `QUOTE_STALE_AFTER_SECONDS`
- **THEN** the response contains a `DATA_STALE` error for that symbol
- **AND** the stale quote is not returned in `quotes`
- **AND** a quote cached for another Provider Mapping is not consulted

### Requirement: Well-formed requests support partial outcomes

The gateway SHALL respond to a well-formed quote request with HTTP status `200` and separate ordered `quotes` and `errors` arrays, even when one or all symbols have symbol-level failures, including `UNSUPPORTED_PROVIDER`.

#### Scenario: All symbols succeed

- **WHEN** every requested symbol has a usable quote
- **THEN** `quotes` contains each distinct symbol in request order
- **AND** `errors` is empty

#### Scenario: Some symbols fail

- **WHEN** at least one requested symbol succeeds and at least one has a symbol-level failure
- **THEN** successful symbols appear in `quotes`
- **AND** failed symbols appear in `errors`
- **AND** the response status is `200`

#### Scenario: All symbols have symbol-level failures

- **WHEN** no requested symbol has a usable quote but the request and registry lookup are valid
- **THEN** `quotes` is empty
- **AND** every failed symbol appears in `errors`
- **AND** the response status is `200`

