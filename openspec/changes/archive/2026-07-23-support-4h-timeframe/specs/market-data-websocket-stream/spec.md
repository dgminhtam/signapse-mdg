## MODIFIED Requirements

### Requirement: The complete subscription is validated before provider access

The gateway MUST validate request shape, the configured distinct-symbol limit, every symbol
against the enabled PostgreSQL registry, and the timeframe against the supported timeframe map
before opening or extending an upstream subscription.

#### Scenario: Symbols parameter is missing or empty

- **WHEN** `symbols` is missing, empty, or contains only commas and whitespace
- **THEN** the gateway closes the downstream connection with WebSocket code `1008`
- **AND** the close reason is `INVALID_SYMBOLS`
- **AND** no provider subscription is opened

#### Scenario: Too many symbols are requested

- **WHEN** the distinct symbol count exceeds `MAX_QUOTE_SYMBOLS`
- **THEN** the gateway closes the downstream connection with WebSocket code `1008`
- **AND** the close reason is `TOO_MANY_SYMBOLS`
- **AND** no provider subscription is opened

#### Scenario: Any symbol is unknown or disabled

- **WHEN** one or more requested symbols have no enabled registry record
- **THEN** the complete subscription is rejected with WebSocket code `1008`
- **AND** the close reason is `UNSUPPORTED_SYMBOL`
- **AND** no partial upstream subscription is opened

#### Scenario: Timeframe is missing or unsupported

- **WHEN** `timeframe` is absent or is not one of `1m`, `5m`, `15m`, `1h`, `4h`, or `1d`
- **THEN** the gateway closes the downstream connection with WebSocket code `1008`
- **AND** the close reason is `UNSUPPORTED_TIMEFRAME`
- **AND** no provider subscription is opened

#### Scenario: Registry validation is unavailable

- **WHEN** PostgreSQL cannot validate the requested symbols
- **THEN** the gateway closes the downstream connection with WebSocket code `1011`
- **AND** the close reason is `DATABASE_UNAVAILABLE`
- **AND** no database detail or credential is exposed

### Requirement: YFINANCE price ticks derive candle events

The gateway SHALL derive YFINANCE stream candles from accepted price ticks for `1m`, `5m`, `15m`,
`1h`, `4h`, and `1d` interests and SHALL use decimal zero volume.

#### Scenario: First tick creates a forming YFINANCE candle

- **WHEN** the first valid tick lands in an active YFINANCE candle timeframe bucket
- **THEN** the adapter emits a `complete=false` candle aligned to the existing UTC timeframe grid
- **AND** sets open, high, low, and close to the tick price
- **AND** sets volume to exact decimal zero

#### Scenario: Later tick updates the current YFINANCE bucket

- **WHEN** another valid tick lands in the same active candle bucket
- **THEN** the adapter preserves open and updates high, low, and close from accepted tick prices
- **AND** emits the updated candle with `complete=false`

#### Scenario: Tick advances to a later bucket

- **WHEN** a valid tick lands after the current candle bucket
- **THEN** the adapter emits the previous bucket with `complete=true`
- **AND** starts and emits the new bucket with `complete=false`
- **AND** does not synthesize skipped buckets

#### Scenario: Yahoo payload includes day volume

- **WHEN** a valid price tick also contains Yahoo day-level or cumulative volume
- **THEN** the adapter does not treat that value as tick or interval candle volume
- **AND** derived candle volume remains decimal zero
