## MODIFIED Requirements

### Requirement: YFINANCE OHLCV rows are normalized strictly

The yfinance adapter SHALL convert valid history rows to repository-owned candle models
using `Decimal` values and UTC datetimes and MUST reject malformed, duplicate, invalid,
or structurally unsafe provider data. An individual row whose only failure is an
inconsistent OHLC envelope MAY be quarantined when at least one other eligible row in
the same non-empty payload is valid; the adapter MUST NOT repair or synthesize that row.

#### Scenario: Valid YFINANCE rows are returned

- **WHEN** yfinance returns valid unique rows inside the requested range
- **THEN** the adapter normalizes open time, close time, OHLC values, and volume
- **AND** it ignores provider fields that are outside the gateway candle model

#### Scenario: YFINANCE row omits volume

- **WHEN** a valid yfinance row has no volume value or has a null volume value
- **THEN** the normalized candle volume is `Decimal("0")`
- **AND** the API serializes it as a fixed-point decimal string

#### Scenario: Isolated YFINANCE OHLC bounds violation is quarantined

- **WHEN** a non-empty yfinance payload contains one row where `High` is below
  `max(Open, Close)` or `Low` is above `min(Open, Close)`
- **AND** at least one other eligible row in the payload has valid timestamp and OHLCV
  values
- **THEN** the adapter excludes the inconsistent row from normalized candles
- **AND** it returns the other valid rows
- **AND** it does not repair, clamp, round, persist, or expose the inconsistent row

#### Scenario: All YFINANCE rows fail only the OHLC bounds check

- **WHEN** a non-empty yfinance payload contains no row that can be normalized because
  every eligible row violates the OHLC bounds check
- **THEN** the adapter raises the sanitized provider-unavailable boundary
- **AND** the failure reason is `INVALID_PAYLOAD`
- **AND** no partial candle result is returned

#### Scenario: YFINANCE payload has a batch-fatal row error

- **WHEN** a yfinance row has an invalid timestamp, duplicate timestamp, missing
  required OHLC field, malformed/non-finite OHLCV value, negative volume, or another
  structural normalization failure
- **THEN** the adapter raises the sanitized provider-unavailable boundary for the
  entire payload
- **AND** it does not continue with a partial result
- **AND** no yfinance DataFrame, exception, or raw provider payload is exposed

### Requirement: Natural YFINANCE provider gaps are preserved

The gateway MUST preserve absent yfinance candle slots as gaps and MUST NOT fabricate
OHLCV candles for omitted provider data or quarantined provider rows.

#### Scenario: Provider returns no candles for a valid range

- **WHEN** a valid yfinance-backed request covers eligible slots for which yfinance
  returns no rows
- **THEN** the gateway returns the valid available candles, which may be an empty list
- **AND** it does not create or persist synthetic candles

#### Scenario: Provider returns only part of a YFINANCE range

- **WHEN** yfinance omits one or more eligible slots but returns other valid rows
- **THEN** the gateway returns and persists only the valid eligible complete rows
- **AND** the omitted eligible slots remain absent

#### Scenario: Provider quarantines one row in a partially valid range

- **WHEN** yfinance returns valid rows together with an isolated OHLC-bounds-invalid row
- **THEN** the gateway returns and persists/cache-merges the valid eligible rows
- **AND** the quarantined row's timestamp remains absent from the response and storage
- **AND** the public response keeps the existing candle response shape
