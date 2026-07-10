## Context

`add-crawl4ai-test-api` introduced a disabled-by-default `POST /internal/crawl` probe that opens one
browser for one URL and either returns one `fitMarkdown` string or fails the request. The next
consumer needs to submit a small URL batch, keep successful Markdown when another URL fails, and
correlate results without relying on completion order. Content cleanup remains the consumer's
responsibility.

This successor change depends on `add-crawl4ai-test-api` being archived so its capability is
available as a main specification baseline.

## Goals / Non-Goals

**Goals:**

- Accept 1 to 10 HTTP(S) URLs in one request to `POST /crawl`.
- Return one stable result object per crawl outcome with its URL, nullable `content`, and nullable
  `error`.
- Preserve successful content when other URLs fail.
- Use Crawl4AI's native batch execution through one request-scoped browser.
- Preserve the feature gate, server-owned crawl defaults, sanitized errors, and optional runtime
  isolation.

**Non-Goals:**

- Preserve the old endpoint or single-URL request contract.
- Guarantee result ordering, deduplicate URLs, or add request/result identifiers.
- Clean, reformat, summarize, or apply source-specific selectors to Markdown.
- Add retries, persistence, scheduling, streaming HTTP responses, workers, or a shared browser.
- Make the endpoint safe for public or multi-tenant use.

## Decisions

### Replace the route without a compatibility alias

Register only `POST /crawl` when `CRAWL_API_ENABLED` is true. Do not retain `/internal/crawl` or
accept the old `url` field because this is an internal test surface and supporting two contracts
would add branching without a migration need.

### Use one strict batch request

Accept `{"urls": ["https://..."]}` with a Pydantic list constrained to 1 through 10 `HttpUrl`
values and continue to reject extra fields. The fixed upper bound protects the browser process
without adding another environment setting; a real workload can propose a configurable limit when
one is measured.

### Return stable per-URL result objects

Return:

```json
{
  "results": [
    {"url": "https://example.com/", "content": "# Example", "error": null},
    {"url": "https://failed.example/", "content": null, "error": "Crawl failed."}
  ]
}
```

Exactly one of `content` and `error` is non-null for each item. The `url` is the normalized URL sent
to Crawl4AI. Response order is unspecified; consumers correlate each item by `url`. A separate
`success` flag was rejected because it duplicates `error is null`, and response IDs were rejected
because the URL already supplies the required correlation.

### Contain URL failures but retain batch-level failure status

An unsuccessful Crawl4AI result or missing fit Markdown becomes an item with `content=null` and the
generic `error="Crawl failed."`. Mixed success/failure and all-item failure responses use HTTP
`200` because the batch operation produced per-URL outcomes.

If browser setup or `arun_many()` raises before per-URL outcomes can be returned, preserve the
existing sanitized HTTP `502`. This distinguishes an unavailable batch executor from ordinary URL
failures without exposing SDK details.

### Use native batch execution and skip ordering work

Create the existing `BrowserConfig()` and fit-Markdown `CrawlerRunConfig` once, open one
`AsyncWebCrawler` context, and call `arun_many(urls=..., config=...)`. Keep the default dispatcher
and crawl configuration. Normalize SDK results behind the provider boundary and return them in the
order supplied by Crawl4AI; no sorting or custom dispatcher is needed because every item contains
its URL.

The provider may use one small provider-owned result record containing `url` and nullable content;
it MUST NOT expose Crawl4AI result or exception types to the API layer. A service layer remains
unnecessary because the route performs only DTO mapping.

## Risks / Trade-offs

- [HTTP `200` can contain only failed items] → Require consumers to inspect each `error` field and
  document the distinction from request-wide `502`.
- [Concurrent browser work increases memory and upstream load] → Cap requests at 10 URLs and keep
  Crawl4AI's default adaptive dispatcher.
- [The endpoint and DTOs are breaking changes] → Update the internal consumer and server together;
  do not maintain a compatibility alias.
- [Response order varies] → Include the normalized input URL in every item and prohibit order-based
  correlation in the contract.
- [Public batch crawling magnifies SSRF exposure] → Keep the existing feature gate and internal-only
  deployment warning.

## Migration Plan

1. Archive `add-crawl4ai-test-api` and sync its specifications.
2. Replace the route and DTO contract, then update the provider to native batch execution.
3. Update focused tests and `docs/spec.md`, including a new curl example.
4. Deploy the updated internal consumer and gateway together.

Rollback restores the single-URL route and provider method. No data migration or cleanup is
required.

## Open Questions

None. Partial result objects, the `/crawl` path, the `content` field, the 10-URL bound, and
request-wide `502` behavior are fixed for this change.
