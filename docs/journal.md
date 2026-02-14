# Phase 3: Application Materials Generator — Development Journal

## Timeline

Phase 3 implemented in a single session, building on the Phase 1+2 foundation of 38 companies, a scoring engine, career page scrapers, job relevance scoring, and 120 passing tests.

## What Was Built

### New Capabilities
1. **Professional profile knowledge base** — 6 new tables for work experiences, projects, skills, education, publications/talks, and application tracking
2. **Interactive interview tool** — `beacon profile interview` walks through a structured questionnaire to populate the profile using Rich prompts
3. **Import/export utility** — Bulk load profile data from JSON, export full profile for backup with roundtrip fidelity
4. **Profile browsing CLI** — Commands to view, list, and browse all profile sections with Rich tables and a completeness dashboard
5. **Anthropic API integration** — First LLM usage in the project; shared client wrapper with `generate()` and `generate_structured()` functions
6. **Resume tailoring engine** — Pipeline: extract requirements from job description → select relevant profile items → generate tailored resume via LLM
7. **Cover letter generator** — Integrates Phase 1 company research (leadership signals, AI signals, tools adopted) with profile data for context-aware cover letters
8. **Application tracking** — Enhanced `job apply` creates application records, `beacon application list/show/update` for status tracking
9. **Supplementary materials** — "Why this company?" statements and portfolio summaries using Phase 1 AI-first signals

### Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM provider | Anthropic Claude via optional `anthropic` SDK | First-party API; clean SDK; optional dependency keeps core lightweight |
| Default model | `claude-sonnet-4-5-20250929` | Good balance of speed and quality for resume/cover letter generation |
| LLM as optional dep | `pip install beacon[llm]` | Profile DB and interview work without API key; LLM features degrade gracefully |
| Doc rendering deps | `pip install beacon[docs]` (python-docx, fpdf2) | Optional; markdown is the primary output format |
| Profile data model | 6 separate tables with FK relationships | Normalized schema; projects FK to work_experiences, applications FK to job_listings |
| Skill upsert | UNIQUE on name, manual check-then-insert/update | Same pattern as job upsert; preserves existing data on re-add |
| JSON arrays | TEXT columns with `json.dumps()` | Same pattern as `match_reasons` in Phase 2; keeps schema simple |
| Interview tool | Separate module from CLI, testable via mock | Rich prompts tested by mocking `Prompt.ask()` and `Confirm.ask()` |
| Section functions lookup | `getattr()` on module for dynamic dispatch | Allows proper mocking in tests (dict references would cache original functions) |

### File Inventory

**18 new files** created, **4 existing files** modified.

#### New source files (10):
- `beacon/db/profile.py` — Profile CRUD operations (all 6 tables)
- `beacon/interview.py` — Interactive profile interview tool
- `beacon/importer.py` — Profile import/export utility
- `beacon/llm/__init__.py` — LLM package re-exports
- `beacon/llm/client.py` — Anthropic API client wrapper
- `beacon/llm/prompts.py` — Prompt templates for all LLM features
- `beacon/materials/__init__.py` — Materials package
- `beacon/materials/resume.py` — Resume tailoring pipeline
- `beacon/materials/renderer.py` — Resume rendering (markdown, docx, pdf)
- `beacon/materials/cover_letter.py` — Cover letter generator
- `beacon/materials/supplementary.py` — Why statements and portfolio summaries

#### New test files (8):
- `tests/test_profile_db.py` — 47 tests for profile CRUD operations
- `tests/test_interview.py` — 14 tests for interview tool
- `tests/test_importer.py` — 17 tests for import/export
- `tests/test_profile_cli.py` — 14 tests for profile CLI commands
- `tests/test_llm.py` — 13 tests for LLM client
- `tests/test_resume.py` — 14 tests for resume tailoring
- `tests/test_cover_letter.py` — 12 tests for cover letter generation
- `tests/test_applications.py` — 12 tests for application tracking

#### Modified files:
- `beacon/db/schema.sql` — Added 6 Phase 3 tables with indexes
- `beacon/db/connection.py` — Updated `reset_db()` drop-order for new tables
- `beacon/cli.py` — Added `profile` and `application` sub-apps with ~15 new commands
- `pyproject.toml` — Added `llm` and `docs` optional dependency groups

## Test Summary

| Phase | Tests |
|-------|-------|
| Phase 1 (companies, scoring, seeding) | 21 |
| Phase 2 (jobs, scanning, adapters, reports) | 99 |
| Phase 3 (profile, LLM, materials, applications) | 154 |
| **Total** | **274** |

## What Was Deferred

- **Embedding-based skill matching** — `select_relevant_items()` uses string matching for skill relevance. Could upgrade to embeddings for semantic matching (e.g., "ML" matching "machine learning").
- **Multi-page PDF layout** — The fpdf2 renderer is basic markdown-to-PDF. A LaTeX-based pipeline would produce publication-quality resumes.
- **Application analytics** — No dashboards or funnel analysis for application outcomes. Could add `beacon application stats` with conversion rates.
- **Template system** — Prompt templates are hardcoded strings. Could support user-customizable templates stored in a config directory.
- **Interview persistence** — The interview tool doesn't support resume/pause. Long interviews must be completed in one session.

## Lessons Learned

1. **`sqlite3.Row` doesn't support `.get()`** — Unlike dicts, Row objects require bracket access. Any code expecting `.get()` on database rows will fail at runtime. Always use `row["field"] or ""` patterns.
2. **`getattr()` dispatch for testability** — Storing function references in a dict breaks mock patching since the dict captures the original reference. Using `getattr(module, func_name)` at call time allows proper mocking.
3. **Optional dependencies need careful testing** — LLM and doc rendering tests must handle `ImportError` gracefully. The `RuntimeError` with install instructions pattern works well for user-facing errors.
4. **Company research context enriches LLM output** — Feeding Phase 1's leadership signals, AI culture signals, and tools adopted into cover letter prompts produces much more specific output than generic templates.
5. **Test connection lifecycle matters** — CLI commands that close connections can interfere with test assertions. Using fresh connections for verification or mocking the close prevents `ProgrammingError: Cannot operate on a closed database`.

---

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
