## Context

`GET /v1/quotes` currently serializes the full normalized `Quote` domain model, including
provider identity, provider symbol, unused nullable fields, and an internal freshness flag. The
initial Java backend only needs the canonical symbol, decimal price, and gateway snapshot time.
Provider mappings and freshness policy remain necessary inside the gateway but are not part of
the consumer's business contract.

## Goals / Non-Goals

**Goals:**

- Expose exactly `symbol`, `price`, and `receivedAt` for every successful quote.
- Keep decimal and UTC serialization stable.
- Preserve existing registry lookup, Binance integration, caching, freshness rejection, partial
  success, and error behavior.
- Make route tests fail if internal quote fields are exposed again accidentally.

**Non-Goals:**

- Simplifying `GET /v1/symbols`, WebSocket events, candle contracts, or error objects.
- Removing provider metadata from domain models, registry records, logs, or adapters.
- Changing the database schema, cache thresholds, SDK operation, or provider selection.

## Decisions

### Use a dedicated minimal API response model

`QuoteResponse` will declare only `symbol`, `price`, and `received_at`, with the existing camel-case
alias producing `receivedAt`. `_to_response` will project those fields from the internal `Quote`.
This preserves a strict boundary without weakening the domain model.

Alternative: remove provider fields from `Quote` itself. Rejected because the service still needs
provider identity and symbol mappings for routing, diagnostics, and future provider support.

### Keep freshness as internal policy

The service will continue using `received_at`, cache TTL, and stale thresholds. A usable cached
quote is returned normally; an expired quote that cannot be refreshed produces `DATA_STALE`.
Consumers therefore receive either a valid minimal quote or a symbol-level error, not a public
freshness flag.

Alternative: return stale quotes without a flag. Rejected because it would hide degraded data.

### Treat the response reduction as a breaking contract change

Documentation and tests will explicitly list the three allowed quote fields. The response
envelope and error format remain unchanged to limit migration work.

## Risks / Trade-offs

- [Existing consumers deserialize removed fields as required] -> Coordinate deployment with the
  internal Java consumer and update its DTO before or alongside the gateway.
- [Provider diagnostics are less visible to API consumers] -> Keep provider metadata in structured
  logs and internal domain objects.
- [Future requirements need removed fields] -> Add only fields with a concrete consumer use case
  through a deliberate contract change.

## Migration Plan

1. Update the route response model, mapper, and contract tests.
2. Update repository documentation to show only the minimal quote representation.
3. Run lint, type checks, and the full test suite.
4. Deploy with the matching Java consumer DTO update.

Rollback consists of restoring the previous response fields; no data or schema rollback is
required.

## Open Questions

None.
