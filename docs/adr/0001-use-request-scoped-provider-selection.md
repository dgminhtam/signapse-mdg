---
status: accepted
---

# Use request-scoped provider selection and provider-owned data identity

An asset may have multiple Provider Mappings but only one Default Provider. A request-wide Provider Override may select any mapping, and the resulting Provider Selection remains fixed for the request or stream while caches, candle history, and stream interests remain isolated by that mapping. Mapping existence means verified support across the complete market-data surface; this avoids capability flags and automatic fallback at the cost of requiring incomplete mappings to be fixed or removed before release.
