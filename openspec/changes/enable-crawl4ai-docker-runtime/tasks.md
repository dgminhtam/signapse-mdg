## 1. Gateway Image Runtime

- [x] 1.1 Update the Docker dependency layer to install the locked `crawl` extra and provision
  Playwright Chromium with its Linux dependencies, without installing the unused Patchright
  browser.
- [x] 1.2 Verify the Docker build command propagates dependency or browser-install failures and
  preserves the existing locked, no-dev installation.

## 2. Dev Compose and Documentation

- [x] 2.1 Enable `CRAWL_API_ENABLED` explicitly for the gateway service in `docker-compose.yml`
  while leaving the application and example-environment defaults false.
- [x] 2.2 Update `docs/deploy-docker.md` with Crawl4AI image prerequisites, build/push/pull/recreate
  commands, import and Chromium checks, `/crawl` smoke verification, and the internal-only warning.
- [x] 2.3 Update `docs/tech-stack.md` to reflect that the dev gateway image now packages the optional
  runtime while default non-Docker installation remains Crawl4AI-free.

## 3. Verification

- [x] 3.1 Validate the resolved Compose configuration and run the existing crawl-focused tests,
  Ruff, and mypy.
- [x] 3.2 Build the `linux/amd64` gateway image and verify Crawl4AI import, headless Chromium launch,
  gateway startup, health, and one `/crawl` request from the built artifact.
