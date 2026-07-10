## 1. Dependency Integration

- [x] 1.1 Add `crawl4ai==0.9.1` to the optional `crawl` project extra.
- [x] 1.2 Regenerate `uv.lock` and review shared transitive version changes.
- [x] 1.3 Verify the default locked production sync succeeds without installing the `crawl` extra.

## 2. Runtime Verification

- [x] 2.1 Install the optional extra and provision its browser runtime with the Crawl4AI setup command.
- [x] 2.2 Verify `crawl4ai` imports on Python 3.14 and `crawl4ai-doctor` completes successfully.
- [x] 2.3 Run the existing pytest, Ruff, and mypy checks to confirm no gateway regression.

## 3. Documentation

- [x] 3.1 Document the pinned optional runtime, `uv` installation, browser setup, and doctor commands in `docs/tech-stack.md`.
- [x] 3.2 Document that this change adds no crawler logic and does not install or initialize Crawl4AI in the default gateway runtime.
