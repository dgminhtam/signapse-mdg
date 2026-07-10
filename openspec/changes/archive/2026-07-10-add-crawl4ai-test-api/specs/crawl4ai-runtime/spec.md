## MODIFIED Requirements

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
