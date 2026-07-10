## Context

MDG currently runs FastAPI on Python 3.14 and locks production dependencies with `uv`. Crawl4AI
brings a headless-browser runtime and a large transitive dependency set, while the current gateway
has no approved crawling workflow. This change prepares and verifies the dependency without making
Chromium part of gateway startup or deployment.

## Goals / Non-Goals

**Goals:**

- Pin and lock one supported Crawl4AI version.
- Make the runtime explicitly installable through `uv`.
- Document browser setup and diagnostics.
- Verify compatibility with Python 3.14 while preserving the default gateway behavior.

**Non-Goals:**

- Crawl URLs or introduce a Crawl4AI adapter, service, worker, route, or lifespan hook.
- Add crawler configuration, persistence, scheduling, retry, or security policy.
- Install browser dependencies in the gateway Docker image.
- Change economic-calendar or public API requirements.

## Decisions

### Use a project optional dependency

Declare a `crawl` extra in `pyproject.toml` and pin Crawl4AI to an exact version, matching the
repository's existing dependency policy. Developers opt in with `uv sync --extra crawl`; the
default gateway installation remains lean.

Adding Crawl4AI to the main dependency list was rejected because every gateway deployment would
pay the dependency and browser-runtime cost before any gateway behavior uses it. A separate
dependency group was rejected because this is a future runtime capability rather than development
tooling.

### Keep browser provisioning explicit

Document `uv run crawl4ai-setup` and `uv run crawl4ai-doctor` for opted-in environments. Do not run
browser provisioning from FastAPI startup or the existing gateway Dockerfile.

Automatic gateway provisioning was rejected because it couples service availability and image
size to an unused browser. A crawler-specific image can be designed with the first executable
crawling workflow.

### Verify the runtime without application scaffolding

The implementation check consists of dependency resolution, a direct package import, Crawl4AI
doctor output, and the repository's existing quality gates. No placeholder adapter or configuration
is added.

Placeholder modules were rejected because they provide no behavior and would pre-commit the next
change to an untested architecture.

## Risks / Trade-offs

- [Crawl4AI or a transitive dependency resolves but fails at runtime on Python 3.14] → Require import
  and doctor verification before completing the change.
- [The optional extra changes shared locked transitive versions] → Run the full existing test,
  lint, and type-check suite after regenerating `uv.lock`.
- [Local browser setup differs from future Linux deployment] → Treat container compatibility as a
  requirement of the later crawler-worker change, where an executable target exists.
- [The dormant dependency becomes stale before crawling logic is added] → Keep the version pinned
  and upgrade only alongside a verified consuming change.

## Migration Plan

1. Add the optional dependency and regenerate `uv.lock`.
2. Install the extra and browser runtime in a development environment.
3. Verify import, doctor, tests, lint, and type checks.
4. Document the opt-in setup and isolation decision.

Rollback removes the optional dependency and regenerates the lock file; application code and data
require no rollback.

## Open Questions

None for this runtime-only change. Worker topology, container image, URL policy, and persistence
belong to the first crawling behavior proposal.
