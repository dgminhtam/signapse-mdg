## REMOVED Requirements

### Requirement: Crawl4AI is an opt-in runtime dependency
The project SHALL pin Crawl4AI in an optional `crawl` dependency extra and SHALL lock its transitive
dependencies with `uv`.

#### Scenario: Developer installs the crawl runtime
- **WHEN** a developer runs `uv sync --extra crawl`
- **THEN** the locked Crawl4AI runtime is installed

#### Scenario: Default gateway dependencies are installed
- **WHEN** the gateway dependencies are installed without the `crawl` extra
- **THEN** Crawl4AI and its browser runtime are not required by the default installation

**Reason**: The gateway no longer has a consumer for the Crawl4AI test surface, so the dependency
and its optional-runtime contract are retired.

**Migration**: Remove Crawl4AI from the project dependency declaration and regenerate `uv.lock`.
There is no replacement extra or crawling runtime.

### Requirement: Crawl4AI runtime setup is documented
The project SHALL document the `uv` commands required to install the optional dependency, provision
its browser runtime, and run its environment diagnostics.

#### Scenario: Developer follows the setup documentation
- **WHEN** a developer prepares a Crawl4AI environment from the repository documentation
- **THEN** the documented commands install the `crawl` extra, run `crawl4ai-setup`, and run
  `crawl4ai-doctor`

**Reason**: No supported Crawl4AI runtime remains in the gateway.

**Migration**: Remove the Crawl4AI setup and diagnostic instructions from current documentation.

### Requirement: Crawl4AI runtime is compatible with the project baseline
The optional Crawl4AI runtime MUST import and pass its environment diagnostics on the project's
Python 3.14 baseline.

#### Scenario: Optional runtime is verified
- **WHEN** the `crawl` extra and browser runtime have been installed
- **THEN** importing `crawl4ai` succeeds
- **AND** `crawl4ai-doctor` completes successfully

**Reason**: The optional runtime is being removed rather than maintained or upgraded.

**Migration**: Replace these checks with the normal locked application import and startup checks;
do not install or verify a browser runtime.

### Requirement: Crawl4AI remains isolated from gateway behavior
The default gateway runtime MUST NOT initialize a browser or require the optional Crawl4AI
dependency. An explicitly enabled internal test API MAY load the optional runtime only while
handling a crawl request.

#### Scenario: Gateway starts with test API disabled
- **WHEN** the gateway starts with `CRAWL_API_ENABLED` false
- **THEN** application startup succeeds without importing Crawl4AI
- **AND** no Crawl4AI browser process is created

#### Scenario: Gateway starts with test API enabled
- **WHEN** the gateway starts with `CRAWL_API_ENABLED` true
- **AND** the optional Crawl4AI runtime is installed
- **THEN** the internal crawl route is registered
- **AND** no browser process is created until the route handles a request

**Reason**: The route and runtime are removed entirely; there is no longer an enabled or disabled
Crawl4AI mode to isolate.

**Migration**: Remove `CRAWL_API_ENABLED`-related Crawl4AI behavior and verify that the application
starts without the dependency or browser assets.
