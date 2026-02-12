# Phase 2: Job Scanner & Monitoring — Development Journal

## Timeline

Phase 2 implemented in a single session, building on the Phase 1 foundation of 38 AI-first companies, a scoring engine, CLI, and 21 passing tests.

## What Was Built

### New Capabilities
1. **Career page scanning** — Automated job listing extraction from Greenhouse API (19 companies), with adapters ready for Lever and Ashby
2. **Generic HTML scraper** — Best-effort extraction using JSON-LD and link pattern heuristics for the 19 "custom" career pages
3. **Job relevance scoring** — 4-dimension scoring engine (title 40%, keywords 30%, location 15%, seniority 15%) tuned for data/analytics/ML roles
4. **Scanner orchestrator** — Full pipeline: fetch -> score -> upsert -> mark stale
5. **CLI commands** — `scan`, `jobs`, `job show/apply/ignore`, `report digest/jobs`
6. **Report generation** — Markdown digest (filtered by date and relevance) and full jobs report
7. **Stats integration** — `beacon stats` and `beacon show` now display job counts and top active jobs

### Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Sync vs async | Sync httpx | 38 companies finishes fast; async adds complexity with no benefit |
| Deduplication | `UNIQUE(company_id, title, url)` + manual upsert | DB-enforced uniqueness; upsert updates `date_last_seen` |
| Job tags | JSON `match_reasons` column | SQLite `json_each()` available for queries; no join complexity |
| Board tokens | Dict in `tokens.py` | Small dataset, easy to maintain, no schema change needed |
| Generic scraper | BeautifulSoup (no Playwright) | JS-heavy pages won't work — acceptable tradeoff |
| Scheduling | External cron calls `beacon scan` | Keeps code testable; scheduling is orthogonal |
| Adapter pattern | ABC + registry factory | Clean extension point for new platforms |

### File Inventory

**19 new files** created, **5 existing files** modified.

#### New source files (10):
- `beacon/db/jobs.py` — Job CRUD operations (upsert, stale marking, queries)
- `beacon/scrapers/base.py` — BaseAdapter ABC
- `beacon/scrapers/greenhouse.py` — Greenhouse boards API adapter
- `beacon/scrapers/lever.py` — Lever postings API adapter
- `beacon/scrapers/ashby.py` — Ashby job board API adapter
- `beacon/scrapers/generic.py` — HTML scraper with JSON-LD and link heuristics
- `beacon/scrapers/tokens.py` — Greenhouse board token mappings
- `beacon/scrapers/registry.py` — Adapter factory
- `beacon/research/job_scoring.py` — Job relevance scoring engine
- `beacon/scanner.py` — Scanner orchestrator

#### New test files (9):
- `tests/test_jobs_db.py` — 19 tests for job DB operations
- `tests/test_adapters.py` — 24 tests for all adapters
- `tests/test_job_scoring.py` — 30 tests for relevance scoring
- `tests/test_scanner.py` — 8 tests for scanner orchestration
- `tests/test_cli.py` — 9 tests for CLI commands
- `tests/test_reports.py` — 9 tests for report generation
- `tests/test_generic_scraper.py` — 7 tests for HTML scraper
- `tests/test_integration.py` — 4 end-to-end tests

#### Modified files:
- `beacon/db/schema.sql` — Added `UNIQUE(company_id, title, url)` constraint
- `beacon/scrapers/__init__.py` — Re-exports `BaseAdapter`, `get_adapter`
- `beacon/cli.py` — Added `scan`, `jobs`, `job`, `report` commands + stats/show updates
- `beacon/export/formatters.py` — Added `export_jobs_digest()`, `export_jobs_report()`
- `README.md` — Phase 2 documentation

## What Was Deferred

- **Playwright/Selenium** — JS-rendered career pages (Workday, etc.) can't be scraped without a browser engine. Deferred to Phase 3 or a future enhancement.
- **Async scanning** — Not needed at 38 companies. Could parallelize with `asyncio` + `httpx.AsyncClient` if the company list grows significantly.
- **Rate limiting** — No rate limiter implemented. The Greenhouse API is permissive, and we scan sequentially. Could add `time.sleep()` or a token bucket if needed.
- **Job description NLP** — The keyword scoring is string matching. Could upgrade to embeddings or a local LLM for better semantic matching.
- **Notification system** — No email/Slack alerts for new relevant jobs. The digest report serves this purpose for now.

## Lessons Learned

1. **The adapter pattern pays off** — Even though only Greenhouse has companies in the seed data, having Lever/Ashby/Generic ready means adding new companies is a config change, not a code change.
2. **Upsert with manual check > ON CONFLICT** — SQLite's `ON CONFLICT` with `UNIQUE` constraint was initially planned, but manual check-then-insert/update gives more control over status preservation (e.g., keeping "applied" status when a job is re-seen).
3. **JSON `match_reasons` > separate tags table** — For a personal tool with SQLite, storing reasons as JSON in the row is simpler and faster than a many-to-many relationship. `json_each()` covers any future query needs.
4. **Test mocking is the right call for HTTP** — All adapter tests use mocked `httpx.get`, making the test suite fast (~15s) and deterministic. Integration tests with real HTTP would be flaky and slow.
