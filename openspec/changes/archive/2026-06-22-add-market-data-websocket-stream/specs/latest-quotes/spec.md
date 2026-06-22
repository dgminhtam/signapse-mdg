## ADDED Requirements

### Requirement: Real-time quote events refresh the shared quote cache
The gateway SHALL update the existing process-local quote cache with every valid normalized
WebSocket quote event before fanout, using the gateway receive time for existing HTTP cache TTL and
freshness calculations.

#### Scenario: Stream event is newer than cached quote
- **WHEN** a valid normalized WebSocket quote event is received for a cached canonical symbol
- **THEN** the cache entry is replaced with the streamed quote
- **AND** a subsequent `GET /v1/quotes` can reuse it under the existing TTL and freshness rules

#### Scenario: Stream event arrives for an uncached quote
- **WHEN** a valid normalized WebSocket quote event is received for an enabled uncached symbol
- **THEN** the quote is inserted into the shared quote cache

#### Scenario: Stream normalization rejects an event
- **WHEN** a provider ticker event cannot be safely normalized
- **THEN** the existing quote cache is not overwritten
- **AND** the HTTP quote response contract remains unchanged

