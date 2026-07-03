## 1. Persistence and Models

- [x] 1.1 Add an Alembic migration for nullable `description` and `news_url` text columns.
- [x] 1.2 Add `description` and `news_url` to the SQLAlchemy economic calendar model.
- [x] 1.3 Add `description` and `news_url` to economic calendar domain models.
- [x] 1.4 Include `description` and `news_url` in repository upsert, change detection, and row mapping.

## 2. Provider Normalization

- [x] 2.1 Change the market-calendar-tool adapter to request `extended=True`.
- [x] 2.2 Normalize `description` from extended specs, preferring the `Measures` row.
- [x] 2.3 Normalize one absolute `news_url` from the first related `/news/.../hit` link.
- [x] 2.4 Keep refresh successful when extended description or news URL is missing.

## 3. HTTP API and Docs

- [x] 3.1 Return `description` and `newsUrl` from `GET /v1/economic-calendar`.
- [x] 3.2 Update `docs/spec.md` with the enriched economic calendar response.

## 4. Tests and Validation

- [x] 4.1 Cover migration/model schema for `description` and `news_url`.
- [x] 4.2 Cover provider parsing for description, news URL, missing fields, and no history persistence.
- [x] 4.3 Cover repository upsert change tracking for enrichment fields.
- [x] 4.4 Cover API response shape including nullable `description` and `newsUrl`.
- [x] 4.5 Run `openspec.cmd validate add-economic-calendar-description-news-url --strict`.
- [x] 4.6 Run focused pytest coverage for economic calendar provider, persistence, repository, and API.
