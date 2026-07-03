## ADDED Requirements

### Requirement: Historical candles can be requested by eligible count

The gateway SHALL allow `GET /v1/candles` clients to request the latest eligible candle slots using
`limit` instead of `from`.

#### Scenario: Count request resolves latest eligible opens

- **WHEN** a client requests an enabled canonical symbol, supported timeframe, valid `limit`, and
  no `from`
- **THEN** the gateway derives the latest `limit` eligible candle opens at or before the resolved
  `to` boundary using the symbol's candle schedule and market-session policy
- **AND** the gateway uses those derived opens for persistence lookup, provider gap fill, cache
  merge, and response filtering

#### Scenario: Count request omits to

- **WHEN** a valid count request omits `to`
- **THEN** the gateway captures current UTC once and uses it as the exclusive upper boundary for
  count derivation, provider access, and response serialization

#### Scenario: Count request crosses closed sessions

- **WHEN** a count request crosses weekends, holidays, maintenance breaks, or pandas calendar break
  windows
- **THEN** closed-session candle opens do not count toward `limit`
- **AND** no provider request is made for closed-session-only sections

#### Scenario: Count request encounters natural provider gaps

- **WHEN** a provider omits one or more derived eligible candle slots
- **THEN** the gateway returns the valid available candles, which can be fewer than `limit`
- **AND** it does not synthesize missing candles or issue provider-specific paging retries to force
  exactly `limit` rows

#### Scenario: Count request uses cached forming candle

- **WHEN** a current cached forming candle matches one of the derived eligible opens
- **THEN** the gateway can merge that candle into the response with `complete=false`
- **AND** it does not persist the forming candle

### Requirement: Historical candle range and count modes are unambiguous

The gateway SHALL treat `from`/`to` range requests and `limit` count requests as distinct request
modes.

#### Scenario: Range request behavior is preserved

- **WHEN** a client supplies `from` and omits `limit`
- **THEN** the gateway preserves the existing half-open `[from,to)` range semantics

#### Scenario: Count request supplies from

- **WHEN** a client supplies both `from` and `limit`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Count request has invalid limit

- **WHEN** `limit` is missing in count mode, non-integer, less than one, or greater than
  `MAX_CANDLES_PER_REQUEST`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`

#### Scenario: Count request keeps response shape

- **WHEN** the gateway returns candles for a valid count request
- **THEN** the response contains the existing `symbol`, `timeframe`, `from`, `to`, and `candles`
  fields
- **AND** `from` is the first derived eligible open when any eligible opens exist
- **AND** `to` is the resolved exclusive upper boundary
