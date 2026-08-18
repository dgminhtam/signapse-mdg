## Why

The gateway no longer has a consumer for its Crawl4AI test surface. Keeping the unused runtime
adds a large browser dependency graph, requires Chromium during Docker builds, and emits a
third-party `SyntaxWarning` during startup. Removing the dead surface reduces deployment cost and
eliminates that warning without changing market-data behavior.

## What Changes

- **BREAKING** Remove the `POST /crawl` endpoint and its request/response contract.
- Remove the Crawl4AI adapter, route DTOs, route-specific tests, and crawl proxy configuration.
- Remove the Crawl4AI dependency and regenerate the lockfile so browser-only transitive packages
  are no longer installed.
- Remove Playwright/Chromium installation from the gateway image and the related deployment smoke
  checks.
- Update current product, deployment, and technology documentation to no longer describe Crawl4AI
  as a gateway capability.
- Retire the current Crawl4AI runtime and test-API specifications while preserving historical
  OpenSpec archive records unchanged.
- Preserve `yfinance==1.6.0`, market-data routes, economic-calendar behavior, and the `newsUrl`
  field; the remaining yfinance WebSocket deprecation warning is intentionally out of scope.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `crawl4ai-runtime`: Retire the Crawl4AI dependency, browser runtime, and deployment setup.
- `crawl4ai-test-api`: Remove the internal batch crawl endpoint and its contract.

## Impact

- Application startup and OpenAPI no longer include the `/crawl` route.
- The dependency lock and Docker image become smaller and no longer require browser provisioning.
- Existing clients of `/crawl` receive a not-found response after deployment; no internal consumer was
  found in the repository.
- No database schema, migration, market-data provider, or economic-calendar API change is required.
