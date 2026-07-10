## Why

MDG needs a minimal internal endpoint to verify that the optional Crawl4AI runtime can turn a
caller-supplied URL into fit Markdown before designing any production crawling pipeline. Keeping
the endpoint opt-in and server-configured prevents this test surface from becoming a generic
public crawler or configuration API.

## What Changes

- Add an opt-in `POST /internal/crawl` endpoint that accepts only a URL and returns only fit
  Markdown.
- Generate fit Markdown with Crawl4AI's default browser and crawl settings plus the required
  default `PruningContentFilter`.
- Keep every Crawl4AI setting in application code or environment settings; reject request fields
  other than `url`.
- Open and close the browser per request for deterministic cleanup in this low-volume test API.
- Hide the route by default behind `CRAWL_API_ENABLED=false` and keep the default gateway runtime
  independent from the optional Crawl4AI extra.
- Return sanitized validation and upstream-failure responses without exposing Crawl4AI details.
- Document and test the internal-only contract.

## Capabilities

### New Capabilities

- `crawl4ai-test-api`: Defines the opt-in internal URL-to-fit-Markdown HTTP contract and its failure
  behavior.

### Modified Capabilities

- `crawl4ai-runtime`: Refines runtime isolation so the default gateway remains Crawl4AI-free while
  an explicitly enabled test API may load the optional runtime per request.

## Impact

- API and application wiring: `app/api/`, `app/main.py`.
- Crawl4AI adapter boundary: `app/providers/`.
- Feature configuration: `app/core/config.py`, `.env.example`.
- Contract documentation and focused unit tests.
- No database, migration, service layer, cronjob, shared browser manager, or production Docker
  change.
- `integrate-crawl4ai-runtime` must be archived before this change is applied or archived so the
  `crawl4ai-runtime` delta has a main specification to modify.
