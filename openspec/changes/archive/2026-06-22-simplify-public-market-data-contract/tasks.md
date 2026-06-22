## 1. Public Quote Contract

- [x] 1.1 Reduce `QuoteResponse` to `symbol`, `price`, and camel-case `receivedAt`.
- [x] 1.2 Update quote response mapping while retaining the richer internal domain model and
  freshness behavior.

## 2. Contract Tests

- [x] 2.1 Update route tests to assert the exact three-field successful quote representation and
  unchanged partial-error envelope.
- [x] 2.2 Update registry integration coverage to verify persisted provider mappings are used
  internally without exposing `providerSymbol`.
- [x] 2.3 Run focused quote service and API tests to confirm cache, stale rejection, ordering, and
  per-symbol errors remain unchanged.

## 3. Documentation

- [x] 3.1 Update `docs/spec.md` examples and semantics for the minimal latest-quotes response.
- [x] 3.2 Update `docs/system-design.md` and `docs/tech-stack.md` to distinguish the rich internal
  quote model from the three-field public DTO.

## 4. Verification

- [x] 4.1 Run Ruff formatting and lint checks.
- [x] 4.2 Run mypy and the full pytest suite.
- [x] 4.3 Verify a live or ASGI `GET /v1/quotes` response exposes no removed fields.
