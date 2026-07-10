## 1. Change Baseline

- [x] 1.1 Archive `add-crawl4ai-test-api`, sync its delta specifications, and verify the
  `crawl4ai-test-api` main spec exists.

## 2. Crawl4AI Batch Adapter

- [x] 2.1 Replace the single-URL provider operation with a typed batch result and one
  request-scoped `arun_many()` call using the existing default browser and fit-Markdown run
  configuration.
- [x] 2.2 Normalize each Crawl4AI result into URL plus nullable content, contain unsuccessful or
  missing-content outcomes per URL, and keep raised browser/batch failures as one adapter error.
- [x] 2.3 Update provider tests for native batch invocation, unchanged configuration, mixed and
  all-item failures, raised batch failures, result order independence, and crawler cleanup.

## 3. Batch HTTP Contract

- [x] 3.1 Replace `/internal/crawl` with `/crawl`, accept only a 1-to-10-item `urls` list, and add
  `results` item DTOs with `url`, nullable `content`, and nullable `error`.
- [x] 3.2 Map provider outcomes to independent result objects with HTTP `200`, while preserving a
  sanitized HTTP `502` for request-wide adapter failures.
- [x] 3.3 Update route tests for the breaking path, strict batch validation, successful and failed
  item correlation by URL, mixed/all failure responses, unspecified order, and sanitized batch
  failures.

## 4. Documentation and Verification

- [x] 4.1 Update `docs/spec.md` with the `/crawl` request, result-object response, 10-URL limit,
  partial-failure semantics, and curl example while retaining the internal-only warning.
- [x] 4.2 Run focused crawl tests, default route-isolation tests, the unit suite, Ruff, and mypy.
