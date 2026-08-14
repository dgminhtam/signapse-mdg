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
