## 1. Persist Enrichment Attempts

- [x] 1.1 Add a migration and SQLAlchemy model mapping for nullable timezone-aware
  `enrichment_attempted_at`.
- [x] 1.2 Add the minimal domain models and repository protocol methods for enrichment candidates and
  enrichment updates.
- [x] 1.3 Update economic calendar upserts so incoming null enrichment preserves stored values and
  does not falsely update `last_changed_at`.
- [x] 1.4 Implement repository selection and pre-fetch marking for incomplete events not attempted in
  the current UTC day.
- [x] 1.5 Add focused repository and persistence tests for null preservation and daily candidate
  throttling.

## 2. Split Base And Detail Fetching

- [x] 2.1 Change regular `market-calendar-tool` calls to use `extended=False` and return normalized
  base events without enrichment.
- [x] 2.2 Add selected-ID detail requests in the gateway adapter using installed `aiohttp`, the
  upstream site mapping, and a concurrency limit of five.
- [x] 2.3 Normalize raw detail `specs` and linked news through the existing description and news URL
  rules while isolating per-event failures.
- [x] 2.4 Update provider tests to verify base-only scraping, candidate-scoped detail URLs, parsing,
  concurrency behavior, and failure isolation.

## 3. Refresh Eligible Events

- [x] 3.1 Update the refresh service to persist base rows before selecting enrichment candidates.
- [x] 3.2 Mark candidates attempted before fetching details, persist non-null detail results, and
  leave failed or empty results unchanged until the next UTC day.
- [x] 3.3 Add refresh service tests covering new, complete, already-attempted, failed, and next-day
  candidates.

## 4. Rollout And Verification

- [x] 4.1 Update API/deployment documentation with base-versus-detail behavior while preserving the
  existing `300` second production interval.
- [x] 4.2 Run the focused economic calendar tests, migration checks, Ruff, mypy, and strict OpenSpec
  validation.
