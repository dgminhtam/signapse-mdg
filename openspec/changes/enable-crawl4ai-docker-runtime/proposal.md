## Why

The dev Compose deployment can enable the Crawl4AI route, but the gateway image installs only the
default dependency set. Enabling `CRAWL_API_ENABLED` therefore crashes application import with
`ModuleNotFoundError: No module named 'crawl4ai'`, and installing the Python package alone would
still leave Chromium unavailable at request time.

## What Changes

- Install the locked optional `crawl` dependency extra in the gateway Docker image.
- Provision Playwright Chromium and its Linux system dependencies during image build so missing
  browser assets fail the build rather than the first crawl request.
- Enable `CRAWL_API_ENABLED` in the repository's dev Compose service while preserving the
  application setting's disabled-by-default behavior outside that deployment.
- Update Docker deployment documentation with the Crawl4AI image requirements, recreate command,
  and import/browser/API verification steps.
- Keep one gateway image and the existing feature gate; do not add a second Dockerfile, build target,
  external browser service, or Patchright browser installation.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `crawl4ai-runtime`: Adds a Docker-packaged Crawl4AI runtime and documented dev Compose enablement
  while preserving optional local installation and disabled startup isolation.

## Impact

- Container build and runtime configuration: `Dockerfile`, `docker-compose.yml`.
- Deployment guidance and smoke checks: `docs/deploy-docker.md`, related runtime documentation.
- The gateway dev image becomes larger and requires network access while building Chromium and its
  Linux packages.
- No API schema, provider logic, database, migration, worker, or public exposure change.
