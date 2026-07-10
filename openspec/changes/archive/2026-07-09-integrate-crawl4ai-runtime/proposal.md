## Why

MDG needs a reproducible, opt-in Crawl4AI runtime before any news crawling behavior is designed or
implemented. Isolating this foundation first lets the project verify Python 3.14, dependency, and
browser compatibility without coupling Chromium to the existing gateway process.

## What Changes

- Add a pinned Crawl4AI optional dependency and lock its transitive dependencies with `uv`.
- Document the opt-in local setup and diagnostic commands for the Crawl4AI browser runtime.
- Verify that the optional runtime imports and passes its environment diagnostics on Python 3.14.
- Keep the default gateway installation, startup, API, persistence, and economic-calendar behavior
  unchanged.

## Capabilities

### New Capabilities

- `crawl4ai-runtime`: Defines the optional dependency, setup, diagnostics, and gateway-isolation
  requirements for the dormant Crawl4AI runtime.

### Modified Capabilities

None.

## Impact

- Dependency metadata and lock file: `pyproject.toml`, `uv.lock`.
- Stack decision documentation: `docs/tech-stack.md`.
- Developer environments may opt into Crawl4AI and its browser dependencies.
- No application modules, routes, settings, migrations, Docker runtime, or public contracts change.
