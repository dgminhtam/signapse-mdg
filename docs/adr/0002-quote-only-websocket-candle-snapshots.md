---
status: accepted
---

# Separate quote streaming from candle snapshots

The market-data WebSocket is a quote-only `Quote Stream`: `WS /v1/stream?symbols=...` emits live quote and lifecycle status events, rejects a `timeframe` query, and no longer opens or persists WebSocket candle interests. Forming and completed candles are obtained through the self-contained `GET /v1/candles` flow with an explicit timeframe, because timeframe belongs to OHLC aggregation rather than to a live quote observation; the REST candle service remains responsible for provider access, a short-lived process-local forming-candle snapshot cache with a default five-second TTL, and completed-candle persistence. Snapshot cache entries are isolated by canonical symbol, Provider Selection, and timeframe; an expired forming entry is evicted rather than relabeled as complete. Polling faster than the TTL is served from cache rather than rejected with a new rate-limit error. The gateway and its internal Java client will migrate together as one coordinated breaking release while keeping the `/v1` paths.
