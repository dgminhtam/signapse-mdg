## Context

The completed `integrate-crawl4ai-runtime` change pins Crawl4AI 0.9.1 as an optional extra and
verifies its browser runtime on Python 3.14, but intentionally adds no application behavior.
Crawl4AI's default Markdown generator produces raw Markdown; fit Markdown requires a content
filter. This change adds the smallest internal HTTP probe that exercises that capability without
turning MDG into a configurable or production crawling service.

The `integrate-crawl4ai-runtime` change must be archived first so its `crawl4ai-runtime`
specification exists as the baseline for this change's delta.

## Goals / Non-Goals

**Goals:**

- Accept one HTTP(S) URL and return one fit-Markdown string.
- Keep browser, crawl, and filtering configuration entirely server-owned.
- Preserve default gateway startup without the optional Crawl4AI dependency.
- Use the existing provider-adapter and FastAPI route patterns with focused tests.

**Non-Goals:**

- Expose raw Markdown, HTML, links, media, screenshots, PDFs, selectors, JavaScript, or extraction
  settings.
- Add persistence, retries, caching policy, batching, scheduling, authentication, or a worker.
- Reuse a browser between requests or install Crawl4AI in the production gateway image.
- Make the endpoint safe for public or multi-tenant use.

## Decisions

### Add an internal, feature-gated route

Use `POST /internal/crawl`, enabled by a new `crawl_api_enabled: bool = False` setting. Conditional
route registration keeps the endpoint absent from both routing and OpenAPI when disabled.

The public `/v1` namespace was rejected because this is a diagnostic surface rather than an MDG
product contract. An always-registered route was rejected because the default installation does
not contain the optional dependency.

### Import the Crawl4AI route only when enabled

Perform the route import inside the enabled branch of `create_app()`. The route can then use normal
top-level Crawl4AI imports while `app.main` remains importable after a default sync without the
`crawl` extra.

Dynamic imports inside every adapter call were rejected because they obscure a deployment error
and add no value once the feature is explicitly enabled.

### Keep the adapter and route, skip a service layer

Place Crawl4AI types and result normalization in `app/providers/crawl4ai_markdown.py`. The route
depends directly on that adapter through a small FastAPI dependency function. There is no
orchestration that justifies a separate service or domain model.

The adapter returns a string and wraps SDK failures in one adapter-owned exception. The route maps
that exception to a sanitized HTTP `502`.

### Use library defaults plus the one configuration required for fit Markdown

Construct:

```text
BrowserConfig()
CrawlerRunConfig(
    markdown_generator=DefaultMarkdownGenerator(
        content_filter=PruningContentFilter()
    )
)
```

Do not set threshold, cache mode, viewport, timeout, user agent, or extraction options. These remain
the pinned library defaults. Do not fall back to raw Markdown when `fit_markdown` is absent because
that would violate the endpoint contract.

BM25 filtering was rejected because the request has no relevance query. LLM filtering was rejected
because it introduces credentials, cost, and nondeterminism.

### Use a request-scoped crawler

Use `async with AsyncWebCrawler(...)` for each request. This is slower than a shared browser but
guarantees cleanup and requires no application lifecycle state, locking, or idle management for a
low-volume test API.

A shared browser should be proposed only if measured startup cost matters for a real crawling
workflow.

### Keep the request and response exact

Use a strict Pydantic request model with `url: HttpUrl` and `extra="forbid"`. Return a camel-case
response model containing only `fit_markdown`, serialized as `fitMarkdown`.

## Risks / Trade-offs

- [Per-request Chromium startup is slow and resource-heavy] → Accept for the test endpoint; replace
  only when a production workload is approved.
- [The endpoint can be abused for SSRF if exposed] → Keep it disabled by default, under `/internal`,
  and document that it must remain local/internal. DNS, redirect, and browser-request controls are
  prerequisites for public exposure.
- [Enabling the route without the optional extra breaks app creation] → Treat this as a clear
  deployment error and document `uv sync --extra crawl` as required.
- [Default pruning can return empty or no fit Markdown on sparse pages] → Return the string when
  present, including an empty string; return sanitized `502` only when the value is absent.
- [Crawl4AI default behavior may change during upgrades] → Keep the dependency pinned and verify
  request and adapter tests with any upgrade.

## Migration Plan

1. Archive `integrate-crawl4ai-runtime`.
2. Add the disabled-by-default setting and conditional route registration.
3. Add the adapter, route contract, and focused tests.
4. Document local setup and internal-only operation.
5. Run tests with and without the optional `crawl` extra to verify default isolation.

Rollback disables the feature flag or removes the conditional route and adapter. No data migration
or cleanup is required.

## Open Questions

None. Public exposure, shared browser lifecycle, and configurable filtering require separate
proposals backed by a real consumer.
