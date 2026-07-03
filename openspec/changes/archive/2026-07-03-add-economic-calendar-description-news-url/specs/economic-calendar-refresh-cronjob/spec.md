## ADDED Requirements

### Requirement: Economic calendar refresh fetches extended event details

The economic calendar provider adapter SHALL use `market-calendar-tool` extended scraping so it can
normalize event descriptions and related news URLs alongside base event values.

#### Scenario: Extended scrape is requested
- **WHEN** the refresh service requests economic calendar events from the provider adapter
- **THEN** the adapter calls `market-calendar-tool` with extended detail retrieval enabled

#### Scenario: Extended detail is missing
- **WHEN** an upstream event has no usable extended description or related news URL
- **THEN** the gateway persists the base event successfully
- **AND** stores `NULL` for the missing enrichment field

### Requirement: Economic calendar refresh normalizes descriptions

The provider adapter SHALL normalize a plain-text description from extended `specs` rows.

#### Scenario: Measures specification is present
- **WHEN** an event has a non-empty extended spec row whose title is `Measures`
- **THEN** the adapter stores that row's text as the event `description`

#### Scenario: Measures specification is absent
- **WHEN** an event has no usable `Measures` spec row
- **AND** another non-empty spec text exists
- **THEN** the adapter stores the first usable spec text by upstream order as `description`

### Requirement: Economic calendar refresh normalizes one related news URL

The provider adapter SHALL normalize at most one related news URL from extended raw news HTML and
MUST NOT store raw news HTML, news text, or full article content.

#### Scenario: Related hit link is present
- **WHEN** an event has related news HTML containing a `/news/.../hit` link
- **THEN** the adapter stores an absolute `news_url` for the first usable hit link

#### Scenario: Related hit link is absent
- **WHEN** an event has no related news HTML containing a usable hit link
- **THEN** the adapter stores `NULL` for `news_url`

#### Scenario: Full article is not crawled
- **WHEN** the adapter stores a related `news_url`
- **THEN** it does not request the news URL
- **AND** it does not store article content
