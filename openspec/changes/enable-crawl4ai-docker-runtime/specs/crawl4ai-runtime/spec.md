## ADDED Requirements

### Requirement: Gateway dev image contains the Crawl4AI runtime
The gateway dev Docker image SHALL install the locked `crawl` dependency extra and SHALL provision
Playwright Chromium with the Linux system dependencies required to launch it.

#### Scenario: Gateway dev image is built
- **WHEN** the repository Dockerfile is built for the deployment platform
- **THEN** importing `crawl4ai` inside the resulting image succeeds
- **AND** Playwright can launch and close headless Chromium

#### Scenario: Browser provisioning fails
- **WHEN** Chromium or its required Linux dependencies cannot be installed
- **THEN** the image build fails
- **AND** the broken image is not treated as deployable

### Requirement: Dev Compose explicitly enables the Crawl4AI API
The repository's dev Compose gateway service SHALL set `CRAWL_API_ENABLED` true while the
application-level setting SHALL remain false by default outside that deployment.

#### Scenario: Dev gateway container starts
- **WHEN** Compose creates the gateway from the Crawl4AI-capable image
- **THEN** application import succeeds with `CRAWL_API_ENABLED` true
- **AND** the crawl route is registered

#### Scenario: Default Python installation starts the gateway
- **WHEN** the application starts outside dev Compose with `CRAWL_API_ENABLED` false
- **THEN** startup does not require importing Crawl4AI
- **AND** no browser process is created

### Requirement: Docker Crawl4AI deployment is documented and verifiable
The project SHALL document how to build, deploy, recreate, and verify the Crawl4AI-capable gateway
image without exposing the crawl route publicly.

#### Scenario: Operator deploys an updated image
- **WHEN** the operator follows the Docker deployment documentation
- **THEN** the commands pull the updated image and recreate the gateway container
- **AND** verification covers application health, Crawl4AI import, Chromium launch, and the crawl
  route

#### Scenario: Operator reviews exposure guidance
- **WHEN** the operator prepares the dev deployment
- **THEN** the documentation retains the internal-only warning
- **AND** identifies SSRF, authentication, and rate limiting as prerequisites for public exposure
