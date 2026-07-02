## ADDED Requirements

### Requirement: Historical candles can be requested by forward eligible count

The gateway SHALL allow `GET /v1/candles` clients to request eligible candle slots forward from an
explicit UTC `from` boundary by supplying `from` and `limit` without `to`.

#### Scenario: Forward count request resolves next eligible opens

- **WHEN** a client requests an enabled canonical symbol, supported timeframe, valid UTC `from`,
  valid `limit`, and no `to`
- **THEN** the gateway derives the next `limit` eligible candle opens at or after `from` using the
  symbol's candle schedule and market-session policy
- **AND** the gateway uses those derived opens for persistence lookup, provider gap fill, cache
  merge, and response filtering

#### Scenario: Forward count request skips closed sessions

- **WHEN** a forward count request crosses weekends, holidays, maintenance breaks, or pandas
  calendar break windows
- **THEN** closed-session candle opens do not count toward `limit`
- **AND** no provider request is made for closed-session-only sections

#### Scenario: Forward count request preserves response shape

- **WHEN** the gateway returns candles for a valid forward count request
- **THEN** the response contains the existing `symbol`, `timeframe`, `from`, `to`, and `candles`
  fields
- **AND** `from` is the first derived eligible open when any eligible opens exist
- **AND** `to` is the exclusive boundary immediately after the final derived eligible open when any
  eligible opens exist

### Requirement: Historical candle count mode query combinations are unambiguous

The gateway SHALL assign a single meaning to each supported `from`, `to`, and `limit` query
combination and MUST reject combinations that mix explicit range and count semantics.

#### Scenario: Explicit range request uses from and to

- **WHEN** a client supplies `from` and `to` without `limit`
- **THEN** the gateway preserves the existing half-open `[from,to)` range semantics

#### Scenario: Forward count request uses from and limit

- **WHEN** a client supplies `from` and `limit` without `to`
- **THEN** the gateway treats the request as forward count mode from `from`

#### Scenario: Backward count request uses to and limit

- **WHEN** a client supplies `to` and `limit` without `from`
- **THEN** the gateway treats the request as backward count mode before `to`

#### Scenario: Backward count request omits boundaries

- **WHEN** a client supplies `limit` without `from` or `to`
- **THEN** the gateway treats the request as backward count mode before one captured request-time
  UTC instant

#### Scenario: Count request supplies both range boundaries

- **WHEN** a client supplies `from`, `to`, and `limit`
- **THEN** the gateway responds with HTTP status `400`
- **AND** the error code is `INVALID_TIME_RANGE`
