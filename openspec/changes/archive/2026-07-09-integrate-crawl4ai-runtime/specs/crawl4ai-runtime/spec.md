## ADDED Requirements

### Requirement: Crawl4AI is an opt-in runtime dependency
The project SHALL pin Crawl4AI in an optional `crawl` dependency extra and SHALL lock its transitive
dependencies with `uv`.

#### Scenario: Developer installs the crawl runtime
- **WHEN** a developer runs `uv sync --extra crawl`
- **THEN** the locked Crawl4AI runtime is installed

#### Scenario: Default gateway dependencies are installed
- **WHEN** the gateway dependencies are installed without the `crawl` extra
- **THEN** Crawl4AI and its browser runtime are not required by the default installation

### Requirement: Crawl4AI runtime setup is documented
The project SHALL document the `uv` commands required to install the optional dependency, provision
its browser runtime, and run its environment diagnostics.

#### Scenario: Developer follows the setup documentation
- **WHEN** a developer prepares a Crawl4AI environment from the repository documentation
- **THEN** the documented commands install the `crawl` extra, run `crawl4ai-setup`, and run
  `crawl4ai-doctor`

### Requirement: Crawl4AI runtime is compatible with the project baseline
The optional Crawl4AI runtime MUST import and pass its environment diagnostics on the project's
Python 3.14 baseline.

#### Scenario: Optional runtime is verified
- **WHEN** the `crawl` extra and browser runtime have been installed
- **THEN** importing `crawl4ai` succeeds
- **AND** `crawl4ai-doctor` completes successfully

### Requirement: Crawl4AI remains isolated from gateway behavior
The change MUST NOT initialize a browser, register application dependencies, or alter HTTP,
WebSocket, persistence, economic-calendar, or startup behavior.

#### Scenario: Gateway starts without the crawl extra
- **WHEN** the gateway starts from its default dependency installation
- **THEN** application startup succeeds without importing Crawl4AI
- **AND** no Crawl4AI browser process is created

