## 1. Runtime Gate

- [x] 1.1 Archive `integrate-crawl4ai-runtime` and verify its `crawl4ai-runtime` main spec exists.
- [x] 1.2 Add disabled-by-default `CRAWL_API_ENABLED` settings and environment documentation.
- [x] 1.3 Conditionally import and register the internal crawl router only when the feature is enabled.
- [x] 1.4 Test that default app creation neither registers the route nor requires the Crawl4AI extra.

## 2. Crawl4AI Adapter

- [x] 2.1 Add a provider-owned adapter that returns fit Markdown using `BrowserConfig()` and a default `PruningContentFilter`.
- [x] 2.2 Map unsuccessful results, missing fit Markdown, and SDK exceptions to one sanitized adapter error.
- [x] 2.3 Test adapter configuration, fit-Markdown normalization, failure mapping, and request-scoped cleanup.

## 3. Internal Test API

- [x] 3.1 Add strict URL-only request and fit-Markdown-only response models for `POST /internal/crawl`.
- [x] 3.2 Wire the route directly to the adapter through a FastAPI dependency and map adapter failures to HTTP `502`.
- [x] 3.3 Test the successful contract, invalid URLs, forbidden extra fields, and sanitized failures.

## 4. Documentation and Verification

- [x] 4.1 Document the internal test endpoint, local opt-in commands, and public-exposure warning in `docs/spec.md`.
- [x] 4.2 Run the focused crawl tests, default gateway tests without the extra, full tests with the extra, Ruff, and mypy.
