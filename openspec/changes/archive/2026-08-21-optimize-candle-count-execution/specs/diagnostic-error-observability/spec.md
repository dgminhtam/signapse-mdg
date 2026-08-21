## ADDED Requirements

### Requirement: Provider-backed count execution is observable by page work

The gateway SHALL emit safe structured diagnostics for provider-backed candle `count` execution.
The diagnostics SHALL include, when applicable, Request ID, canonical symbol, Provider Identifier,
provider symbol, timeframe, count direction, Eligible Candle Slots scanned, page count, logical
provider call count, source row counts, stop reason, and calendar, database, and provider elapsed
times.  These fields SHALL remain internal and SHALL NOT change the public candle response.

#### Scenario: Completed count query records aggregate work

- **WHEN** a provider-backed count query completes with a full, partial, or empty result
- **THEN** the gateway emits a structured diagnostic event with the applicable count-page work and
  latency fields
- **AND** the event identifies whether execution stopped after satisfying the Candle Count, history
  exhaustion, or Candle Count Scan Budget exhaustion

#### Scenario: Count provider failure retains safe page context

- **WHEN** a selected provider fails while resolving a provider-backed count page
- **THEN** the gateway emits the existing safe provider-failure diagnostic context together with
  applicable count-page work and elapsed-time fields
- **AND** the event does not expose provider payloads, credentials, DSNs, or unrestricted
  exception text

#### Scenario: Count cancellation does not start later pages

- **WHEN** a caller cancels a provider-backed count query during execution
- **THEN** the gateway records the applicable count-page progress safely
- **AND** it does not record or start a later page as completed work after cancellation
