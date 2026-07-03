## Context

The economic calendar refresh currently calls `market-calendar-tool` with `extended=False`, so only
base event fields are persisted and exposed. `market-calendar-tool` can fetch per-event details with
`extended=True`; those details include `specs` rows and related `news` HTML snippets.

## Goals / Non-Goals

**Goals:**

- Persist a plain-text event `description`.
- Persist one related `news_url` that downstream consumers can crawl themselves.
- Expose both fields through the existing `/v1/economic-calendar` response.
- Keep the provider adapter resilient to missing or malformed extended-detail fields.

**Non-Goals:**

- Do not persist history rows; `previous` remains enough for current product needs.
- Do not persist raw news HTML, full news text, article content, or arrays of news links.
- Do not crawl external news articles.
- Do not add JSONB fields or new dependencies.

## Decisions

- Use `market-calendar-tool` with `extended=True`.
  - Alternative considered: call the package's detail endpoint manually per event.
  - Rationale: the package already owns the detail URL shape and concurrent fetching.
- Store `description TEXT NULL` and `news_url TEXT NULL` on `economic_calendar_events`.
  - Alternative considered: JSONB for specs/news/history.
  - Rationale: the requested public shape is scalar, and two nullable text columns are the smallest
    useful schema.
- Normalize description from `result.specs`.
  - Prefer the first non-empty row whose `title` is `Measures`; otherwise use the first non-empty
    spec text by `order`.
  - Rationale: `Measures` is the concise event meaning; storing every spec line is noisier than the
    API needs.
- Normalize news URL from raw `result.news.html`.
  - Parse the first anchor whose `href` contains `/news/` and ends with `/hit`, then make it
    absolute using the upstream site host.
  - Alternative considered: store cleaned news text from `clean_news()`.
  - Rationale: cleaned text loses reliable link structure, and downstream only needs the crawl URL.
- Avoid relying on `market-calendar-tool.clean_data()` for extended details.
  - Rationale: observed extended `specs` can omit columns expected by the package cleaner; the
    gateway adapter should normalize only the fields it uses.

## Risks / Trade-offs

- Extended scraping performs one detail fetch per event -> keep the existing fixed refresh window
  and supported type set; revisit only if refresh latency or upstream pressure becomes a problem.
- Detail rows may be absent for some events -> persist `NULL` description/news URL and keep base
  event refresh successful.
- Upstream HTML structure can change -> isolate parsing in the provider adapter and cover it with
  focused tests.
