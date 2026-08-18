## 1. Remove the application surface

- [x] 1.1 Delete the Crawl4AI route module, adapter module, and their route/provider DTOs and error types.
- [x] 1.2 Remove Crawl4AI route import and registration from the application factory.
- [x] 1.3 Remove `crawl_proxy_url` from typed settings and `CRAWL_PROXY_URL` from Docker Compose.

## 2. Remove dependency and browser runtime

- [x] 2.1 Remove `crawl4ai` from the project dependency declarations.
- [x] 2.2 Regenerate `uv.lock` with the remaining dependency graph and verify locked sync succeeds.
- [x] 2.3 Remove Playwright/Chromium installation from the Dockerfile and delete Crawl4AI-specific
  deployment smoke commands.

## 3. Remove obsolete tests and current documentation

- [x] 3.1 Delete the Crawl4AI route and provider unit tests.
- [x] 3.2 Remove the Crawl4AI API, runtime, browser setup, and dependency references from current
  product, deployment, and technology documentation.
- [x] 3.3 Remove the current `crawl4ai-runtime` and `crawl4ai-test-api` main specifications while
  leaving historical OpenSpec change archives unchanged.

## 4. Verify the removal

- [x] 4.1 Verify the application factory imports and starts without Crawl4AI, and `/crawl` is absent
  from OpenAPI and returns `404`.
- [x] 4.2 Run the full unit suite, Ruff, and mypy; confirm market-data and economic-calendar behavior
  remains covered.
- [x] 4.3 Build the locked gateway image without browser provisioning and verify the remaining startup
  and health checks.
- [x] 4.4 Scan active source, dependency, Docker, documentation, and current-spec paths for stale
  Crawl4AI/Playwright/CRAWL_PROXY references, excluding historical archives.
