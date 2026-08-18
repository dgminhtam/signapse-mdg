# Market Data Gateway

The Market Data Gateway provides canonical market data independently of upstream provider-specific identifiers.

## Language

**Provider Override**:
An explicit request-level choice to source market data for every requested asset from a configured provider mapping instead of each asset's default provider.
_Avoid_: Custom provider, per-symbol provider

**Supported Provider**:
A provider for which an asset has a configured provider mapping and verified support across the gateway's complete market-data surface. A supported provider remains eligible for Provider Override whether or not it is the asset's default provider.
_Avoid_: Active provider, globally supported provider

**Default Provider**:
The supported provider selected for an asset when a request does not specify a Provider Override.
_Avoid_: Only provider, enabled provider

**Provider Identifier**:
The stable, case-sensitive name by which a market-data provider is selected, such as `YFINANCE` or `TWELVE_DATA`.
_Avoid_: Provider alias, lowercase provider name

**Provider Mapping**:
The association between a canonical asset, a Provider Identifier, and that provider's symbol for the asset. One mapping identifies the asset's Default Provider; every mapping identifies a Supported Provider.
_Avoid_: Provider fallback, provider alias

**Provider Selection**:
The Provider Mapping resolved for one request or stream subscription. A selection remains fixed for that operation even if the asset's Default Provider changes.
_Avoid_: Live provider switch, mutable provider selection

**Provider Availability**:
The temporary operational ability of a Supported Provider to serve market data. Availability does not determine whether the provider is supported for an asset.
_Avoid_: Provider support, configured mapping

**Historical Price Resolution**:
The provider-specific policy for selecting the nearest eligible completed candle price at or before a requested instant. The policy may use a coarser timeframe when finer historical data is unavailable, without using later market data or changing the selected Provider Mapping.
_Avoid_: One-minute historical price, cross-provider fallback

**Request ID**:
A bounded correlation identifier assigned to one REST request or WebSocket handshake. A valid inbound `X-Request-ID` is preserved; missing or unsafe values are replaced with a generated UUID and echoed in the response header.
_Avoid_: Job ID, provider request ID

**Job ID**:
A generated correlation identifier for a standalone cron or backfill execution that has no HTTP request. It is scoped to that background run and is never presented as a REST request ID.
_Avoid_: Request ID, run number

**Failure Reason**:
The internal stable diagnostic classification for an operational failure, such as `TIMEOUT`, `RATE_LIMITED`, `AUTH_FAILED`, `INVALID_PAYLOAD`, or `DATABASE_QUERY_FAILED`. It is not exposed in public error bodies.
_Avoid_: Public error code, raw provider message

**Diagnostic Event**:
A structured JSON log record with a stable event name and safe contextual fields used to investigate runtime behavior. It may contain provider and request/job context but never raw provider payloads, credentials, DSNs, or unrestricted exception text.
_Avoid_: API response, audit record

**Quote Stream**:
A real-time subscription that delivers normalized price observations for canonical assets. It represents live quote updates and does not itself define an OHLC aggregation interval.
_Avoid_: Candle stream, timeframe stream

**Candle Snapshot**:
The OHLC state returned for a canonical asset and requested timeframe at one point in time. A snapshot may represent either a forming candle or a completed candle.
_Avoid_: Live price, quote tick

**Eligible Candle Slot**:
A timeframe opening timestamp permitted by an asset's market-session policy, whether or not an upstream candle exists for that timestamp.
_Avoid_: Candle row, available candle

**Provider-backed Candle Snapshot**:
A candle snapshot whose OHLCV values are backed by an upstream provider observation and retained by the gateway as forming or completed data.
_Avoid_: Synthetic candle, fabricated candle

**Candle Count**:
An upper bound on Provider-backed Candle Snapshots selected from a directional anchor; the result may contain fewer snapshots when history is exhausted or unavailable.
_Avoid_: Slot limit, exact row guarantee

**Candle Count Scan Budget**:
The maximum number of Eligible Candle Slots that a count query may inspect while searching for Provider-backed Candle Snapshots. Reaching this budget may produce a partial result and never justifies synthetic candles.
_Avoid_: Candle count, provider row limit

**Candle History Window**:
A UTC half-open interval used to select candle snapshots by their opening timestamp; the lower boundary is included and the upper boundary is excluded.
_Avoid_: Candle overlap range, visual chart window
