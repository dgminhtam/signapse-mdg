## Why

Clients need the gateway to expose the shared historical candle intervals supported across the
current providers. The public contract should cover the agreed eight timeframe strings and keep
provider-native interval names behind adapter boundaries.

## What Changes

- Add public candle timeframes `30m`, `1w`, and `1mo` to `GET /v1/candles`, for the full supported
  set: `1m`, `5m`, `15m`, `30m`, `1h`, `1d`, `1w`, `1mo`.
- Map every supported public timeframe to provider-specific intervals inside existing candle
  adapters.
- Preserve the existing response shape, half-open range filtering, persistence identity, and stable
  error envelope.
- Keep realtime/WebSocket candle subscriptions for weekly/monthly out of scope.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `historical-candles`: Extend supported historical candle timeframes to the agreed eight-value
  gateway set.

## Impact

- Affected API: `GET /v1/candles` accepts `timeframe=30m`, `timeframe=1w`, and `timeframe=1mo`.
- Affected code: timeframe registry, candle schedule/gap calculation, provider interval mapping,
  Twelve Data/yfinance/Binance candle adapter tests as applicable, and docs.
- Affected persistence: no schema change; all candles use the existing
  `(provider, provider_symbol, timeframe, open_time)` identity.
