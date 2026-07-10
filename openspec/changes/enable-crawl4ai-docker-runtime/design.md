## Context

The gateway Dockerfile currently runs `uv sync --locked --no-dev`, while Crawl4AI 0.9.1 is pinned
under the optional `crawl` extra. `create_app()` imports the crawl route only when
`CRAWL_API_ENABLED=true`; enabling that setting in the current image therefore fails at startup
before Uvicorn can serve traffic. A usable Crawl4AI image also needs a Playwright Chromium binary
and its Linux shared-library dependencies.

The repository has one dev gateway image and one Compose service. The crawl route remains an
internal test surface, and the application setting must continue to default to false outside the
explicit dev Compose deployment.

## Goals / Non-Goals

**Goals:**

- Make the existing gateway dev image capable of importing Crawl4AI and launching its default
  Chromium browser.
- Enable the crawl route explicitly in the repository's dev Compose service.
- Fail image construction when required Python or browser assets cannot be installed.
- Document build, deploy, recreate, and smoke-verification commands.

**Non-Goals:**

- Add a second Dockerfile, build target, sidecar, remote browser, or shared browser lifecycle.
- Install the Patchright browser used only by Crawl4AI's undetected mode.
- Change the crawl API contract, feature-gate default, or provider configuration.
- Make the crawl route publicly safe or add SSRF/auth/rate-limit controls.
- Fix the unrelated economic-calendar upstream 403 failure.

## Decisions

### Package the optional extra in the single dev gateway image

Change the dependency layer to `uv sync --locked --no-dev --extra crawl`. Local and non-Docker
default installations remain unchanged, while the published dev image carries the runtime needed
when Compose explicitly enables the route.

A separate crawl image or build target was rejected because this repository deploys one internal
dev gateway and does not yet have a second workload or lifecycle to justify parallel image paths.

### Install only the browser used by the current provider

After dependency sync, run:

```text
uv run python -m playwright install --with-deps chromium
```

The provider uses Crawl4AI's default Playwright Chromium path. Calling the Playwright module
directly installs the browser plus Debian dependencies and propagates a non-zero exit if setup
fails. `crawl4ai-setup` was rejected for the image because Crawl4AI 0.9.1 also attempts an unused
Patchright installation and converts browser-install failures to warnings, allowing a broken image
to build successfully.

No browser volume or path override is needed while the image builds and runs as its existing root
user. If the image later adopts a non-root runtime user, browser ownership and path should be
revisited in that separate hardening change.

### Enable the route only in dev Compose

Set `CRAWL_API_ENABLED: "true"` on the Compose gateway service. Do not change the Pydantic setting
default or `.env.example` default; importing the app after a normal dependency sync must remain
Crawl4AI-free.

The route remains bound to the existing internal interface. Deployment documentation must retain
the warning that public exposure needs SSRF controls, authentication, and rate limiting.

### Verify the built artifact, not only source configuration

Deployment checks should cover three boundaries:

1. `docker compose config` resolves the enabled environment value.
2. A container created from the image imports `crawl4ai` and launches/closes headless Chromium.
3. After `docker compose up -d --force-recreate gateway`, health and `/crawl` smoke requests succeed.

`docker compose restart` is insufficient after changing image or environment because it does not
recreate the container.

## Risks / Trade-offs

- [Chromium and Linux packages substantially increase image size and build time] → Accept for the
  single dev image; split images only when a non-crawl production image is actually required.
- [Browser installation depends on external package and browser repositories] → Run it during build
  so failure blocks publishing rather than surfacing at request time.
- [Enabling `/crawl` expands SSRF exposure] → Keep the current internal bind and deployment warning;
  do not publish the port without separate controls.
- [Cross-platform build can hide architecture mismatches] → Continue building the deployment image
  explicitly for `linux/amd64` and run browser smoke checks from that image.

## Migration Plan

1. Update the Docker dependency/browser layer and dev Compose flag.
2. Update runtime and deployment documentation.
3. Build and smoke-test the `linux/amd64` image locally before pushing.
4. Pull the image on the dev server and recreate the gateway container.
5. Verify health, route registration, and one `/crawl` request.

Rollback sets `CRAWL_API_ENABLED=false` for immediate recovery or redeploys the previous image. No
database migration or cleanup is required.

## Open Questions

None. A single Crawl4AI-capable dev image and Playwright-only Chromium installation are fixed for
this change.
