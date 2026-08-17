# Quote-only stream and candle snapshot release

Release this gateway change together with the Java client. This is a breaking internal MVP
release; there is no mixed-version compatibility window or feature flag.

## Java client contract

The quote stream URL is:

```text
/v1/stream?symbols=BTC/USD,ETH/USD
/v1/stream?symbols=BTC/USD,ETH/USD&provider=TWELVE_DATA
```

The client MUST omit `timeframe` from quote-stream URLs. If an old URL contains the parameter,
the gateway closes it with WebSocket code `1008` and reason
`TIMEFRAME_NOT_ALLOWED`.

The client consumes only:

- quote events with `type=quote`, `symbol`, `price`, and `receivedAt`;
- status events whose `channels` is exactly `["quote"]` and whose states are
  `CONNECTING`, `SUBSCRIBED`, `STALE`, `RECONNECTING`, or `ERROR`.

For an initial quote, the client calls `GET /v1/quotes`; the WebSocket does not send an initial
snapshot. For a candle snapshot, the client calls:

```text
GET /v1/candles?symbol=TSLA&timeframe=1m&limit=1
```

The candle response shape is unchanged. A forming result has `complete=false`; completed data
continues through the normal PostgreSQL/provider candle path.

## Release sequence

1. Build and validate the gateway and Java client from the same release pair.
2. Deploy the gateway and Java client during one maintenance window.
3. Verify quote-only subscriptions, quote lifecycle statuses, and `GET /v1/candles?limit=1`
   without an active WebSocket.
4. Confirm old clients are no longer connecting with `timeframe` and no client expects candle
   events from the stream.

## Rollback

If the contract or provider behavior is invalid, roll back the gateway and Java client together to
the previous matching release. Do not run the new gateway with the old client or the old gateway
with the new client. The forming snapshot cache is process-local and has no database or shared-cache
migration, so rollback requires no data migration.

