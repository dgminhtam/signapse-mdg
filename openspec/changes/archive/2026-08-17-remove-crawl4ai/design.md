## Context

The gateway currently imports the Crawl4AI route from the application factory, exposes an
always-registered `POST /crawl` test surface, and imports Crawl4AI at the route boundary. The
project dependency list and lockfile install Crawl4AI together with its browser-related graph, and
the Dockerfile provisions Playwright Chromium for that route.

Repository search found no internal caller for the route. The feature is therefore a dormant test
surface rather than part of the market-data product. The removal must preserve the market-data
provider graph, economic-calendar behavior, and the existing `newsUrl` field.

## Goals / Non-Goals

**Goals:**

- Remove the Crawl4AI route and adapter from the gateway.
- Remove the direct dependency, browser provisioning, proxy setting, and Crawl4AI-only tests.
- Regenerate the lockfile from the remaining declared dependencies.
- Retire current Crawl4AI specifications and documentation while preserving historical archives.
- Verify the gateway starts and exposes the unchanged market-data and economic-calendar surfaces.

**Non-Goals:**

- Change yfinance or its accepted WebSocket deprecation warning.
- Remove or change economic-calendar `newsUrl` data.
- Replace Crawl4AI with another crawler or HTTP scraping library.
- Change market-data routes, provider mappings, database schema, or migrations.
- Rewrite completed or archived historical OpenSpec artifacts.

## Decisions

### Remove the route instead of retaining a stub

Delete the `/crawl` route, its DTOs, adapter, and route registration. A `404` after deployment is
acceptable because the user confirmed there is no consumer. Retaining a `410`, `501`, or compatibility
stub would preserve an unused contract and keep unnecessary branching.

### Remove the entire browser dependency path

Delete Crawl4AI from the project dependencies and regenerate `uv.lock`; do not hand-edit individual
transitive package entries. Remove the Docker Playwright/Chromium installation because no remaining
application code imports Playwright. The lock resolver decides which shared transitive packages are
still needed by other dependencies.

### Remove route-specific configuration and tests

Delete `crawl_proxy_url` and `CRAWL_PROXY_URL` after the route is gone. Delete tests whose only
purpose is to validate the removed route or adapter. Keep the existing market-data, economic-calendar,
and general application-factory tests.

### Update current specifications, not history

Use removal deltas for the current `crawl4ai-runtime` and `crawl4ai-test-api` capabilities. Remove
their current product/deployment documentation. Leave `openspec/changes/archive/` and other
historical change records unchanged so the reason for the old capability remains auditable.

### Verify at the highest seams

Verify removal through the application factory/OpenAPI surface and the resolved dependency/Docker
surface. The key checks are that `/crawl` is absent, the application imports without Crawl4AI, the
locked sync succeeds without browser provisioning, and existing tests/lint/type checks pass.

Alternatives rejected:

- Keeping the endpoint as a deprecation stub: no consumer exists and it would preserve the dead
  dependency boundary.
- Suppressing the Crawl4AI warning: this hides unused code instead of removing it.
- Moving Crawl4AI to a separate image: no crawling workload remains to justify a second runtime.

## Risks / Trade-offs

- [An untracked external caller may depend on `/crawl`] → Treat removal as an explicit breaking
  change and verify the deployment consumer inventory before release.
- [Lock regeneration removes a package that another dependency needs] → Run a locked sync and the
  full test/lint/type-check suite after resolution.
- [Documentation and current specs can retain stale Crawl4AI references] → Search active source,
  dependency, Docker, documentation, and current-spec paths; exclude historical archives from the
  zero-reference check.

## Migration Plan

1. Remove the route, adapter, configuration, tests, dependency declaration, and browser install step.
2. Regenerate and validate `uv.lock`.
3. Update current docs and remove the current Crawl4AI capability specifications.
4. Run the application-factory/OpenAPI checks, full unit suite, Ruff, mypy, and the locked Docker
   build/smoke checks that remain relevant.
5. Deploy the new image; no database migration or data backfill is required.

Rollback restores the previous application image and dependency lock if an undocumented consumer is
discovered. No persistent data changes are involved.

## Open Questions

None. The endpoint removal, archive policy, preserved `newsUrl` field, and accepted yfinance warning
were confirmed before proposal creation.
