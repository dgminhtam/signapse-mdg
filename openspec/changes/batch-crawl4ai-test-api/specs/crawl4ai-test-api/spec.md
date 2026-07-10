## MODIFIED Requirements

### Requirement: Crawl4AI test API is opt-in
The gateway SHALL register the Crawl4AI test route only when `CRAWL_API_ENABLED` is true, and that
setting SHALL default to false.

#### Scenario: Test API is disabled
- **WHEN** the gateway starts with `CRAWL_API_ENABLED` false
- **THEN** `POST /crawl` is not registered

#### Scenario: Test API is enabled
- **WHEN** the gateway starts with `CRAWL_API_ENABLED` true
- **AND** the optional Crawl4AI runtime is installed
- **THEN** `POST /crawl` is registered
- **AND** `POST /internal/crawl` is not registered

### Requirement: Crawl request has a minimal contract
The test API SHALL accept a JSON object containing only `urls`, where `urls` contains 1 through 10
HTTP or HTTPS URLs, and MUST NOT accept Crawl4AI configuration from the caller.

#### Scenario: Valid URL batch
- **WHEN** the caller posts `{"urls": ["https://example.com", "https://crawl4ai.com"]}` to `/crawl`
- **THEN** the gateway attempts to crawl both URLs

#### Scenario: Invalid URL batch
- **WHEN** the caller submits a missing list, an empty list, more than 10 URLs, a non-HTTP URL, or an
  invalid URL
- **THEN** the gateway returns HTTP `422`

#### Scenario: Caller supplies the old contract or crawl configuration
- **WHEN** the request contains `url` or any field other than `urls`
- **THEN** the gateway returns HTTP `422`

### Requirement: Test API returns fit Markdown
The gateway SHALL return HTTP `200` with `results`, a list containing one result object for each
per-URL crawl outcome. Each object SHALL contain the normalized input `url`, nullable `content`, and
nullable `error`; exactly one of `content` and `error` SHALL be non-null. Response ordering is
unspecified, and callers MUST correlate content by `url` rather than list position.

#### Scenario: URL crawl succeeds
- **WHEN** Crawl4AI successfully produces fit Markdown for a URL
- **THEN** that URL's result contains the fit Markdown in `content`
- **AND** its `error` is null

#### Scenario: URL crawl fails
- **WHEN** Crawl4AI reports failure or produces no fit Markdown for one URL
- **THEN** that URL's result contains `content` as null
- **AND** its `error` is `"Crawl failed."`
- **AND** successful results for other URLs remain in the response

#### Scenario: All URL crawls fail individually
- **WHEN** Crawl4AI produces a per-URL failure outcome for every requested URL
- **THEN** the gateway returns HTTP `200`
- **AND** every result contains its own generic error

#### Scenario: Batch results complete out of order
- **WHEN** Crawl4AI completes URLs in an order different from the request
- **THEN** every result still identifies its content or error by `url`
- **AND** the gateway does not promise request-order output

### Requirement: Crawl failures are sanitized
The test API MUST NOT expose Crawl4AI exceptions, upstream response bodies, local paths, or browser
details in either item errors or request-wide failures.

#### Scenario: One Crawl4AI result fails
- **WHEN** Crawl4AI returns an unsuccessful result for one URL
- **THEN** the gateway returns the generic error `"Crawl failed."` only for that URL's item
- **AND** the response remains HTTP `200`

#### Scenario: Batch execution fails before outcomes are available
- **WHEN** browser setup or batch execution raises before the gateway can produce per-URL outcomes
- **THEN** the gateway returns HTTP `502`
- **AND** the response contains only a generic crawl-failure message

### Requirement: Browser resources are request-scoped
The test API SHALL use one request-scoped Crawl4AI browser context for the URL batch and SHALL close
it when the request completes.

#### Scenario: Batch request completes
- **WHEN** a batch crawl request succeeds, contains URL-level failures, or fails request-wide
- **THEN** the request-scoped crawler is closed

#### Scenario: Batch request is executed
- **WHEN** the provider receives the validated URL list
- **THEN** it submits the list through Crawl4AI's native batch operation using the server-owned run
  configuration
