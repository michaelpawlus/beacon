# Beacon

[![CI](https://github.com/michaelpawlus/beacon/actions/workflows/ci.yml/badge.svg)](https://github.com/michaelpawlus/beacon/actions/workflows/ci.yml)

**AI-First Job Search Platform**

A curated, evidence-backed database of companies where AI tools aren't just allowed — they're expected. Every entry includes public evidence of leadership buy-in, tool adoption, and cultural integration — plus automated job scanning, relevance scoring, and LLM-powered application materials.

> Most job boards tell you *who's hiring*. Beacon tells you *who's building the future* — and helps you apply.

## Why This Exists

LinkedIn Jobs surfaces thousands of listings, but it can't tell you whether a company's CEO has mandated AI usage, whether engineers actually use Claude Code or Copilot, or whether "AI-first" in the job description means anything beyond a buzzword. Beacon can.

Every company in this database is scored on five dimensions:
- **Leadership Buy-in** (30%) — Has the CEO/CTO publicly committed to AI-first operations?
- **Tool Adoption** (25%) — Which AI tools are required, encouraged, or allowed?
- **Culture** (25%) — Is AI-first in the DNA? Engineering blogs, employee reports, job posting language.
- **Evidence Depth** (10%) — How much verifiable evidence do we have?
- **Recency** (10%) — How recent are the signals?

## Quick Start

```bash
# Clone and install (uv installs the pinned Python automatically)
git clone https://github.com/michaelpawlus/beacon.git
cd beacon
uv sync

# Initialize database with seed data (38 companies)
uv run beacon init

# List all companies by AI-first score
uv run beacon companies

# Show detailed info for a company
uv run beacon show Shopify

# Export as markdown
uv run beacon export markdown

# Export as CSV or JSON
uv run beacon export csv --output companies.csv
uv run beacon export json --min-score 7
```

## Phase 2: Job Scanner

Beacon now scans career pages for job listings, scores them for relevance, and generates reports.

```bash
# Install scraping dependencies
uv sync --extra scraping

# Scan all career pages
beacon scan

# Scan specific company or platform
beacon scan --company Anthropic
beacon scan --platform greenhouse

# List jobs sorted by relevance
beacon jobs
beacon jobs --min-relevance 7 --status active
beacon jobs --company Anthropic

# View job details
beacon job show 42

# Track application status
beacon job apply 42
beacon job ignore 99

# Generate reports
beacon report digest --since 2025-03-01 --min-relevance 7
beacon report jobs --output jobs-report.md
```

### Architecture

```
beacon scan
    │
    ├─ Adapter Registry ─── Greenhouse API (19 companies)
    │                    ├── Lever API (future)
    │                    ├── Ashby API (future)
    │                    └── Generic HTML scraper (19 companies)
    │
    ├─ Job Relevance Scoring
    │   ├── Title match (40%)
    │   ├── Keyword match (30%)
    │   ├── Location (15%)
    │   └── Seniority (15%)
    │
    └─ DB: upsert + stale marking
```

### Supported Platforms

| Platform | Method | Companies |
|----------|--------|-----------|
| Greenhouse | Public JSON API | 19 |
| Lever | Public JSON API | 0 (ready for additions) |
| Ashby | Public JSON API | 0 (ready for additions) |
| Custom | HTML scraping (JSON-LD + link heuristics) | 19 |

## Phase 3: Application Materials Generator

Beacon generates tailored application materials using your professional profile + Phase 1 company research + Claude LLM.

```bash
# Install LLM dependencies
uv sync --extra llm

# Optional: PDF and DOCX rendering
uv sync --extra docs

# Set your Anthropic API key
export ANTHROPIC_API_KEY=sk-ant-...
```

### Profile Management

```bash
# Build your profile interactively
beacon profile interview
beacon profile interview --section work    # just work experiences

# Or bulk-import from JSON
beacon profile import profile.json

# Export for backup
beacon profile export --output backup.json

# Browse your profile
beacon profile show                         # full summary
beacon profile work                         # work experiences
beacon profile projects                     # projects
beacon profile skills                       # skills by category
beacon profile education                    # education
beacon profile publications                 # publications & talks
beacon profile stats                        # completeness dashboard
```

### Resume & Cover Letter Generation

```bash
# Generate a tailored resume for a specific job
beacon profile resume 42
beacon profile resume 42 --format pdf --output resume.pdf
beacon profile resume 42 --format docx --pages 2

# Generate a cover letter (uses Phase 1 company research)
beacon profile cover-letter 42
beacon profile cover-letter 42 --tone conversational --output letter.md
```

### Application Tracking

```bash
# Apply to a job (creates application record)
beacon job apply 42

# Track applications
beacon application list
beacon application list --status interview
beacon application show 1
beacon application update 1 --status interview --notes "Phone screen scheduled"
```

### How It Works

```
beacon profile resume <job_id>
    │
    ├─ Extract requirements from job description (LLM)
    ├─ Select relevant profile items (skill/tech matching)
    ├─ Build company context (Phase 1 signals)
    └─ Generate tailored resume via Claude API
```

Cover letters incorporate Phase 1 research — leadership signals, AI culture evidence, and tools adopted — for company-specific content that goes beyond generic templates.

## Current Data

The seed dataset includes 38 companies across four tiers:

| Tier | Description | Example Companies |
|------|-------------|-------------------|
| 🟢 Tier 1 | AI-Native | Anthropic, Cursor, Vercel, Replit, Databricks |
| 🔵 Tier 2 | AI-First Converts | Shopify (Tobi's mandate), Klarna, Duolingo |
| 🟡 Tier 3 | Strong Adoption | Stripe, Notion, GitLab, Ramp, Scale AI |
| ⚪ Tier 4 | Emerging Signals | DoorDash, Brex, Together AI, Hex |

## Scoring

The composite score (0–10) is computed from verifiable public signals:

```
Composite = Leadership × 0.30 + Tools × 0.25 + Culture × 0.25 + Evidence × 0.10 + Recency × 0.10
```

Run `beacon show <company>` to see the full breakdown for any company.

## Phase 4: Professional Presence Automation

Beacon generates multi-platform content from your profile data — GitHub README, LinkedIn content, blog posts, and personal website pages.

```bash
# Generate a GitHub profile README
beacon presence github
beacon presence github --output README.md

# LinkedIn content
beacon presence linkedin-headline       # generate 5 headline options
beacon presence linkedin-about          # generate About section
beacon presence linkedin-post --topic "Rolling out AI at scale"

# Blog content
beacon presence blog-outline --topic "Building AI agents for non-technical users"
beacon presence blog-generate --topic "Data warehouse modernization lessons"
beacon presence blog-export 1 --format medium     # export for Medium
beacon presence blog-export 1 --format devto       # export for Dev.to

# Content management
beacon presence drafts                  # list all drafts
beacon presence draft 1                 # view a draft
beacon presence publish 1 --url "..."   # mark as published

# Content calendar
beacon presence calendar                # list planned content
beacon presence calendar-add --title "AI Post" --platform linkedin --date 2025-07-01
beacon presence calendar-seed           # auto-generate calendar from AI ideas

# Personal website (Astro-ready)
beacon presence site-generate           # export all content to site/src/content/
beacon presence site-resume             # generate resume page
beacon presence site-projects           # generate project pages

# Enrichment interviews
beacon presence enrich                  # capture accomplishments with STAR framework
beacon presence enrich --work-id 1      # enrich a specific work experience
beacon presence enrich --list-gaps      # show missing profile information
beacon presence enrich --generate-content  # auto-generate content from interview
```

### How It Works

```
beacon presence github
    │
    ├─ Build profile context (work, skills, projects, education)
    ├─ Apply platform-specific template
    ├─ Generate via Claude API
    ├─ Adapt for platform format (markdown, char limits, frontmatter)
    └─ Auto-save as content draft
```

Content adapters handle platform constraints:
- **LinkedIn:** Strip markdown, enforce 3,000 char post limit / 2,600 char about limit
- **GitHub:** Ensure proper GFM spacing
- **Blog:** Add YAML frontmatter for Astro
- **Medium:** Remove frontmatter, convert H1 to H2
- **Dev.to:** Liquid tags frontmatter, max 4 tags

## Phase 5: Integration & Polish

Phase 5 wires everything together into a cohesive daily-use tool.

```bash
# Configuration
beacon config init                     # create default config
beacon config show                     # view current settings
beacon config set min_relevance_alert 7.0

# Unified Dashboard
beacon dashboard                       # full dashboard with all sections
beacon dashboard --compact             # compact view

# Feedback Tracking
beacon application outcome 1 --outcome phone_screen --days 5
beacon application outcomes            # list all outcomes
beacon application effectiveness       # view effectiveness analysis

# Notifications & Automation
beacon automation test-notify          # test notification delivery
beacon automation run                  # full scan → notify cycle
beacon automation run --scan-only      # scan only
beacon automation run --digest-only    # digest only
beacon automation cron install --every 6   # schedule via cron
beacon automation cron status
beacon automation log                  # view run history

# Agent Orchestration
beacon automation agents               # run all agents
beacon automation agents --dry-run     # preview agent plans
beacon automation agents-status        # recent agent runs

# Scoring Feedback Loop
beacon report scoring-feedback         # calibration report
beacon report variant-effectiveness    # resume variant analysis

# Onboarding
beacon guide                           # quick-start guide
```

### Architecture

```
beacon dashboard
    │
    ├─ Company Watchlist (Phase 1 data, sorted by score)
    ├─ Top Job Matches (Phase 2 data, sorted by relevance)
    ├─ Application Pipeline (Phase 3 data, by status)
    ├─ Presence Health (Phase 4 data, freshness indicators)
    ├─ Content Pipeline (drafts, calendar, overdue items)
    ├─ Feedback Summary (outcome distribution)
    └─ Action Items (auto-generated priorities)

beacon automation run
    │
    ├─ Scan all career pages (Phase 2)
    ├─ Filter by min_relevance_alert
    ├─ Send notifications (email + desktop)
    └─ Log to automation_log

beacon automation agents
    │
    ├─ ResearchAgent: refresh stale company signals
    ├─ JobAnalystAgent: re-score borderline jobs (4-7)
    └─ ApplicationPrepAgent: create drafts for unapplied matches
```

## Project Roadmap

Beacon is the foundation for a larger job search automation platform:

- [x] **Phase 1:** Company Intelligence Database
- [x] **Phase 2:** Job Scanner — monitor career pages, score relevance, generate reports
- [x] **Phase 3:** Application Generator — profile knowledge base, LLM-powered resume/cover letter generation, application tracking
- [x] **Phase 4:** Professional Presence — content generation, enrichment interviews, personal website export
- [x] **Phase 5:** Integration & Polish — dashboard, feedback loops, notifications, automation, agent orchestration

## Documentation

- [Onboarding Guide](docs/onboarding-guide.md) — step-by-step setup
- [Best Practices](docs/best-practices.md) — recommended cadences
- [User Roadmap](docs/user-roadmap.md) — building momentum over time
- [Phase 5 Journal](docs/phase-5-journal.md) — development notes

## Contributing Signals

Know about a company's AI adoption that isn't in the database? Contributions welcome:

1. Open an issue with the company name and evidence URL
2. Or submit a PR adding to `beacon/db/seed.py`

Every signal needs a public, verifiable source (blog post, tweet, news article, job posting).

## Tech Stack

- **Python 3.11+** with type hints
- **SQLite** — zero infrastructure, portable, version-controllable
- **Typer + Rich** — professional CLI with beautiful output
- **httpx + BeautifulSoup4** — career page scanning (optional)
- **Anthropic Claude API** — resume/cover letter generation (optional)
- **python-docx + fpdf2** — PDF/DOCX rendering (optional)

## License

MIT
