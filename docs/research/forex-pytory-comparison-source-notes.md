# Forex-Pytory comparison source notes

Snapshot taken 2026-09-14 from the public repository's `main` head, commit
[`8f6985d011b8a9da8bcd7998534db01206655626`](https://github.com/AtaCanYmc/forex-pytory/commit/8f6985d011b8a9da8bcd7998534db01206655626).
The repository metadata reports `main` as the default branch and a last push on
2026-06-16; the published release is `v0.1.0` ([repository metadata](https://api.github.com/repos/AtaCanYmc/forex-pytory),
[release](https://github.com/AtaCanYmc/forex-pytory/releases/tag/v0.1.0)). Findings below come from
the pinned source and recursive tree; no package was installed or executed.

## What it provides

Forex-Pytory is a synchronous BeautifulSoup/cloudscraper scraper with four
hard-coded sites: ForexFactory, CryptoCraft, EnergyExch, and MetalsMine. Each
wrapper builds a site URL and calls the shared parser ([ForexFactory wrapper](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/src/forex_pytory/core/scraper/forex_factory_scraper.py#L11-L29);
the other wrappers have the same shape in the [pinned tree](https://api.github.com/repos/AtaCanYmc/forex-pytory/git/trees/8f6985d011b8a9da8bcd7998534db01206655626?recursive=1)).

The public event model has only eight optional string fields: `id`, `time`,
`currency`, `event`, `forecast`, `actual`, `previous`, and `impact`. The model
uses aliases such as `ID` and `Time`, but does no domain validation beyond
Pydantic construction ([models.py](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/src/forex_pytory/core/models.py#L5-L17)).
The parser reads the optional row attribute `data-event-id` (configurable by
environment), skips rows without a usable event name, and normalizes impact to
`low`, `medium`, `high`, or `n/a` ([parser.py](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/src/forex_pytory/core/scraper/_parser.py#L13-L22),
[row normalization](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/src/forex_pytory/core/scraper/_parser.py#L295-L361)). IDs are therefore raw, optional provider row IDs with no source namespace or identity/history fields.

## Gaps against our market-calendar-tool integration

| Area | Forex-Pytory at the pinned commit | Implication for this gateway |
| --- | --- | --- |
| Range and dates | URL helpers accept a `timeline`, but parsing extracts one start date and then iterates rows; date-header rows are skipped without advancing the base date ([parser.py](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/src/forex_pytory/core/scraper/_parser.py#L364-L390)). | It is adequate for a one-day scrape, but is unsafe as a replacement for the adapter's explicit `start`/`end` range fetch. |
| Timezone | Converts 12/24-hour text into a naive `datetime`, applies `DEFAULT_HOUR_OFFSET = 0`, and formats it as `DD/MM/YYYY HH:MM`; malformed/unknown times fall back to the previous timestamp ([time.py](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/src/forex_pytory/core/scraper/_time.py#L9-L67), [constants.py](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/src/forex_pytory/core/scraper/_constants.py#L18-L21), [utils.py](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/src/forex_pytory/core/scraper/_utils.py#L13-L21)). | It cannot provide the gateway's timezone-aware/UTC `scheduled_at` contract safely. Silent timestamp fallback is also risky for persistence. |
| Detail/news/history | No `description`, `news`, revision, or event-history model is present. The sitemap helper returns only URL and `lastmod` metadata ([sitemap.py](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/src/forex_pytory/core/scraper/forexfactory_sitemap.py#L60-L88)). The README claims news capability ([README.md](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/README.md#L16-L30)), but no event-detail/news endpoint exists in the pinned source tree. | Our adapter already normalizes `revision`, better/worse values, descriptions and `news_url`, and fetches missing detail data separately ([local adapter](../../app/providers/market_calendar_tool.py#L101-L260), [local domain](../../app/domain/economic_calendar.py#L6-L24)). Forex-Pytory cannot supply those fields. |
| Sync/async | `get_page_html` uses blocking `cloudscraper` with a default 10-second timeout; `get_records` does not expose a timeout and there is no retry/backoff or retryable-error classification ([HTTP helper](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/src/forex_pytory/core/scraper/_http.py#L7-L20), [wrapper](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/src/forex_pytory/core/scraper/forex_factory_scraper.py#L18-L29)). | The MCP handler is declared `async` but directly calls this blocking path ([server.py](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/src/forex_pytory/mcp/server.py#L47-L90)); use in an ASGI service would block the event loop. Our adapter offloads the SDK scrape to a thread, sets a 30-second request override, and maps failures to `ProviderUnavailableError` ([local adapter](../../app/providers/market_calendar_tool.py#L49-L99)). |
| API surface | CLI/MCP accept one source and one optional `YYYY-MM-DD` date; MCP exposes one tool, `fetch_economic_events`, and returns failures as text content ([server.py](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/src/forex_pytory/mcp/server.py#L22-L90)). | It has no gateway-style typed range/filter/error contract. |

## Packaging, tests, and maintenance

`pyproject.toml` declares version `0.1.0`, Python `>=3.9`, and all dependencies as
runtime dependencies; it declares no optional dependency groups ([pyproject.toml](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/pyproject.toml#L5-L29)).
The README nevertheless instructs `pip install -e .[mcp,cli]` ([README.md](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/README.md#L34-L43)), so those extras are not defined by the pinned project metadata. The MCP module also imports `src.forex_pytory...` while the build is configured to discover `forex_pytory` below `src`; this is a source-level risk for a non-editable installed wheel ([server.py](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/src/forex_pytory/mcp/server.py#L9-L14), [pyproject.toml](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/pyproject.toml#L28-L29)). README version badges also say `v1.0.0`, while package and MCP server versions are `0.1.0` ([README.md](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/README.md#L6-L10)).

The pinned recursive tree has no `tests/` directory ([tree API](https://api.github.com/repos/AtaCanYmc/forex-pytory/git/trees/8f6985d011b8a9da8bcd7998534db01206655626?recursive=1)). CI runs lint and a Python 3.10/3.11/3.12 matrix, but creates an empty `tests` directory and explicitly turns pytest failures into success with `|| echo`; the safety scan is similarly non-blocking ([ci.yml](https://github.com/AtaCanYmc/forex-pytory/blob/8f6985d011b8a9da8bcd7998534db01206655626/.github/workflows/ci.yml#L48-L110)). GitHub Actions shows the latest CI and release run succeeded at the pinned commit, after earlier CI failures ([workflow runs](https://api.github.com/repos/AtaCanYmc/forex-pytory/actions/runs?per_page=10)). The repository's commit list contains 13 commits, all on 2026-06-16 ([commit API](https://api.github.com/repos/AtaCanYmc/forex-pytory/commits?per_page=100)), so there is little maintenance history to rely on.

## Assessment

Forex-Pytory overlaps with the four market sites and could be useful as a
prototype for HTML parsing. It is not a drop-in replacement for the pinned
`market-calendar-tool` integration: it lacks explicit range/timezone handling,
source-scoped identity and history, detail/news enrichment, typed failure
semantics, retries, and non-blocking I/O. Replacing the current SDK would
require building those gateway contracts around or inside it, plus fixing the
packaging and test-enforcement gaps above.
