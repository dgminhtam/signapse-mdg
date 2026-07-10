## Why

The current Crawl4AI test endpoint handles only one URL, so callers must create multiple HTTP
requests and lose successful work when treating several crawls as one operation. MDG needs a
minimal batch contract that correlates every result by URL and contains failures to the affected
item.

## What Changes

- **BREAKING** Replace `POST /internal/crawl` with `POST /crawl`.
- **BREAKING** Replace the single `url` request field with a strict `urls` list containing 1 to 10
  HTTP(S) URLs.
- **BREAKING** Replace the top-level `fitMarkdown` string with `results`, a list of objects containing
  `url`, nullable `content`, and nullable `error` fields.
- Return one result object per crawl outcome without guaranteeing response order; callers correlate
  outcomes by `url`.
- Return successful and failed URL outcomes together with HTTP `200`; a URL-level failure uses a
  generic item error and does not discard other content.
- Reserve a sanitized HTTP `502` for request-wide browser or batch-execution failures that prevent
  per-URL outcomes from being produced.
- Crawl the URLs through Crawl4AI's native batch API using one request-scoped browser while keeping
  all existing server-owned browser, crawl, and pruning defaults.
- Keep the route disabled by default and document and test the revised internal-only contract.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `crawl4ai-test-api`: Changes the enabled route, request and response schemas, batch execution,
  result correlation, and partial-failure behavior.

## Impact

- Breaking internal API contract in `app/api/routes_crawl.py` and `docs/spec.md`.
- Batch result normalization in `app/providers/crawl4ai_markdown.py`.
- Focused provider and route tests in `tests/unit/`.
- No new dependency, service layer, persistence, worker, retry policy, source-specific cleaning, or
  public exposure.
- The completed `add-crawl4ai-test-api` change must be archived before this change is applied or
  archived so the `crawl4ai-test-api` main specification exists as its baseline.
