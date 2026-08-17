## REMOVED Requirements

### Requirement: Crawl4AI test API is opt-in
The gateway SHALL register the internal Crawl4AI test route only when
`CRAWL_API_ENABLED` is true, and that setting SHALL default to false.

#### Scenario: Test API is disabled
- **WHEN** the gateway starts with `CRAWL_API_ENABLED` false
- **THEN** `POST /internal/crawl` is not registered

#### Scenario: Test API is enabled
- **WHEN** the gateway starts with `CRAWL_API_ENABLED` true
- **AND** the optional Crawl4AI runtime is installed
- **THEN** `POST /internal/crawl` is registered

**Reason**: The Crawl4AI test surface has no consumer and is being deleted, including its current
batch route.

**Migration**: Remove the route. Clients must stop calling the internal crawl surface; no
replacement endpoint is provided.

### Requirement: Crawl request has a minimal contract
The test API SHALL accept a JSON object containing only an HTTP or HTTPS `url` and MUST NOT accept
Crawl4AI configuration from the caller.

#### Scenario: Valid URL request
- **WHEN** the caller posts `{"url": "https://example.com"}` to `/internal/crawl`
- **THEN** the gateway crawls that URL

#### Scenario: Invalid URL request
- **WHEN** the caller submits a missing URL, a non-HTTP URL, or an invalid URL
- **THEN** the gateway returns HTTP `422`

#### Scenario: Caller supplies crawl configuration
- **WHEN** the request contains any field other than `url`
- **THEN** the gateway returns HTTP `422`

**Reason**: The request contract belongs only to the removed Crawl4AI test API.

**Migration**: Remove request validation and the endpoint contract with the route.

### Requirement: Test API returns fit Markdown
The gateway SHALL return a successful JSON response containing only the generated fit Markdown.

#### Scenario: Crawl succeeds
- **WHEN** Crawl4AI successfully produces fit Markdown
- **THEN** the gateway returns HTTP `200`
- **AND** the response is `{"fitMarkdown": "<generated markdown>"}`

#### Scenario: Fit Markdown is unavailable
- **WHEN** the crawl succeeds without producing a fit Markdown value
- **THEN** the gateway returns HTTP `502` with a sanitized error

**Reason**: The gateway no longer generates or returns Crawl4AI Markdown.

**Migration**: Remove the response DTO and all fit-Markdown normalization.

### Requirement: Fit Markdown configuration is server-owned
The gateway SHALL construct Crawl4AI with default browser and crawl settings and SHALL add a
`DefaultMarkdownGenerator` using a default `PruningContentFilter` so fit Markdown is produced.

#### Scenario: Server executes a crawl
- **WHEN** the adapter crawls a valid URL
- **THEN** it uses `BrowserConfig()` defaults
- **AND** it uses `CrawlerRunConfig` with
  `DefaultMarkdownGenerator(content_filter=PruningContentFilter())`
- **AND** no request value changes that configuration

**Reason**: The adapter and all browser/crawl configuration are removed.

**Migration**: Remove the Crawl4AI configuration and provider boundary; no alternate crawler is
introduced.

### Requirement: Crawl failures are sanitized
The test API MUST NOT expose Crawl4AI exceptions, upstream response bodies, local paths, or browser
details.

#### Scenario: Crawl4AI reports failure
- **WHEN** Crawl4AI returns an unsuccessful result or raises an exception
- **THEN** the gateway returns HTTP `502`
- **AND** the response contains only a generic crawl-failure message

**Reason**: There is no longer a crawl request or Crawl4AI failure boundary in the gateway.

**Migration**: Remove the Crawl4AI error type, route handler, and crawl-specific error mapping.

### Requirement: Browser resources are request-scoped
The test API SHALL open and close its Crawl4AI browser resources for each request.

#### Scenario: Request completes
- **WHEN** a crawl request succeeds or fails
- **THEN** the request-scoped crawler is closed

**Reason**: The route and browser runtime are removed.

**Migration**: Remove request-scoped browser lifecycle code and browser smoke tests.

### Requirement: Test API remains internal-only
The project SHALL document the Crawl4AI endpoint as a local/internal test surface that MUST NOT be
enabled on a publicly reachable gateway.

#### Scenario: Operator reviews deployment guidance
- **WHEN** the operator prepares a gateway deployment
- **THEN** the documentation identifies `CRAWL_API_ENABLED=false` as the default
- **AND** warns that public enablement requires SSRF controls for DNS, redirects, and browser
  subrequests

**Reason**: The endpoint is removed rather than exposed under a different access policy.

**Migration**: Remove the crawl endpoint deployment and SSRF guidance; retain unrelated deployment
security guidance.
