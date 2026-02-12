# AI-First Job Search Platform — Full Roadmap

## Project Codename: **Beacon**

> A personal job search system that curates AI-first companies, monitors their openings, auto-generates application materials, and maintains your professional presence across LinkedIn, GitHub, and a personal website — all powered by the same agentic workflows you'd be hired to build.

---

## Core Philosophy

This project is not just a tool — it **is** the portfolio. Every component demonstrates the exact skills AI-first companies want to see: agentic architecture, practical AI implementation, data engineering, and the ability to ship functional software fast. The system eats its own cooking.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     BEACON PLATFORM                         │
├─────────────┬──────────────┬──────────────┬────────────────┤
│  Company    │  Job         │  Application │  Professional  │
│  Intel DB   │  Scanner     │  Generator   │  Presence      │
├─────────────┼──────────────┼──────────────┼────────────────┤
│ SQLite DB   │ Career page  │ Resume       │ Personal site  │
│ AI-first    │ scrapers     │ tailoring    │ (Next.js/Hugo) │
│ evidence    │ RSS/API      │ Cover letter │ GitHub repos   │
│ scoring     │ monitors     │ gen          │ LinkedIn sync  │
│ Leadership  │ Cadence      │ Portfolio    │ Blog posts     │
│ signals     │ scheduler    │ matching     │ Project cards  │
└──────┬──────┴──────┬───────┴──────┬───────┴───────┬────────┘
       │             │              │               │
       └─────────────┴──────────────┴───────────────┘
                           │
                    ┌──────┴──────┐
                    │  Unified    │
                    │  Data Layer │
                    │  (SQLite)   │
                    └─────────────┘
```

---

## Phase 1: Company Intelligence Database + Foundation

**Goal:** Build the curated database of AI-first employers with evidence-backed scoring. Stand up the project repo as a public portfolio piece.

**Timeline:** ~1–2 weeks

### 1.1 — AI-First Company Research & Schema

- Design SQLite schema for companies:
  - `companies` — name, domain, careers_url, hq_location, remote_policy, size_bucket, industry
  - `ai_signals` — company_id, signal_type, source_url, excerpt, date_observed, signal_strength (1-5)
  - `leadership_signals` — company_id, leader_name, title, quote/action, source_url, date
  - `tools_adopted` — company_id, tool_name (Claude Code, Codex, Cursor, Copilot, etc.), evidence_url, adoption_level (encouraged/required/allowed)
  - `company_scores` — composite AI-first score computed from signals
- Signal types to track:
  - CEO/CTO public statements about AI adoption
  - Engineering blog posts about AI workflows
  - Job postings that mention AI tools as requirements
  - Conference talks / podcasts from leadership
  - Glassdoor/Blind mentions of AI-first culture
  - GitHub activity showing AI tool usage
  - Press coverage of AI initiatives

### 1.2 — Initial Company Seeding

- Web research to populate initial 30–50 companies across tiers:
  - **Tier 1 (AI-native):** Anthropic, OpenAI, Cognition (Devin), Cursor, Vercel, Replit, etc.
  - **Tier 2 (AI-first converts):** Shopify (Tobi's AI mandate), Klarna, Duolingo, etc.
  - **Tier 3 (Strong AI adoption):** Stripe, Netflix, Spotify, Databricks, etc.
  - **Tier 4 (Emerging signals):** Companies where leadership is publicly bought-in but adoption is still scaling
- Each company requires at minimum:
  - 1 leadership signal (CEO/CTO quote or policy)
  - 1 tool adoption evidence point
  - 1 culture signal (blog post, job posting language, employee reports)
- Compute composite AI-first score (weighted formula)

### 1.3 — Project Repository & Portfolio Setup

- Initialize public GitHub repo: `beacon-job-search` (or similar)
- README with architecture diagram, philosophy, tech choices
- Clean commit history showing thoughtful development
- License choice (MIT or similar)
- This repo itself becomes a portfolio piece

### 1.4 — CLI / Simple Interface

- Python CLI to query the database:
  - `beacon companies list --min-score 8`
  - `beacon companies add --interactive`
  - `beacon signals add --company "Shopify" --type leadership --url "..."`
- Export capabilities (JSON, CSV, Markdown table)

### Deliverables
- [ ] SQLite database with schema and seed data
- [ ] Python package with CLI
- [ ] Public GitHub repo with professional README
- [ ] Markdown report: "50 Most AI-First Companies (2025)" — publishable as blog post

---

## Phase 2: Job Scanner & Monitoring

**Goal:** Automated monitoring of career pages for target companies, with smart filtering and notification.

**Timeline:** ~2 weeks after Phase 1

### 2.1 — Career Page Scraping Infrastructure

- For each company, identify career page structure:
  - Direct career pages (Greenhouse, Lever, Ashby, Workday, etc.)
  - API-based job boards (Greenhouse API is excellent, Lever has one too)
  - Custom career pages requiring scraping
- Build adapters per ATS platform:
  - `GreenhouseAdapter` — API-based, cleanest
  - `LeverAdapter` — API-based
  - `AshbyAdapter` — API-based
  - `GenericScraperAdapter` — Playwright/BeautifulSoup fallback
- Store job listings in SQLite:
  - `job_listings` — company_id, title, url, location, department, description_text, date_posted, date_first_seen, date_last_seen, status (active/closed)
  - `job_tags` — job_id, tag (remote, hybrid, senior, IC, manager, etc.)
  - `job_match_scores` — job_id, relevance_score, match_reasons

### 2.2 — Smart Filtering & Scoring

- Role matching based on your target profiles:
  - Data Scientist / ML Engineer
  - AI/ML Engineering Manager
  - AI Strategy / Solutions Architect
- Keyword scoring (positive: "agentic", "Claude", "LLM", "data platform"; negative: "5+ years React", "Java only")
- Location filter (remote, hybrid in Columbus-accessible areas)
- Seniority inference from title and description
- LLM-based relevance scoring for edge cases

### 2.3 — Scheduling & Notifications

- Cron-based or scheduled scanning (daily or every few hours)
- Lightweight notification system:
  - Email digest (weekly or on new high-match jobs)
  - Optional: Slack webhook, SMS, or push notification
- Dashboard view (simple HTML or CLI report) of:
  - New jobs since last scan
  - Top matches with scores
  - Company activity trends

### Deliverables
- [ ] ATS adapter framework with 3-4 adapters
- [ ] Job listing database with scoring
- [ ] Scheduled scanner (cron or similar)
- [ ] Notification pipeline
- [ ] Dashboard or report generator

---

## Phase 3: Application Materials Generator

**Goal:** Given a job listing, auto-generate tailored resume, cover letter, and any supplementary materials using your full professional history.

**Timeline:** ~2 weeks after Phase 2

### 3.1 — Professional History Knowledge Base

- Structured data store of everything you've done:
  - `work_experiences` — role, org, dates, description, key_achievements, technologies, metrics
  - `projects` — name, description, technologies, outcomes, repo_url, is_public, sanitized_description
  - `skills` — name, category, proficiency, evidence (projects/roles that demonstrate it)
  - `education` — degrees, certifications, relevant coursework
  - `publications_talks` — blog posts, presentations, panels
- This is your "canonical resume database" — richer than any single resume
- Import from existing resume + manual enrichment
- Projects can be added from work (sanitized) or personal GitHub

### 3.2 — Resume Tailoring Engine

- Base resume template(s) in structured format
- For each job listing:
  - Extract key requirements and preferences
  - Select most relevant experiences, projects, and skills
  - Rewrite bullet points to align with job language
  - Generate tailored 1-page and 2-page versions
  - Output as PDF and DOCX
- A/B variant generation (different emphasis strategies)

### 3.3 — Cover Letter Generator

- Company research integration (pull from Company Intel DB)
- Job-specific narrative generation
- Multiple tone options (formal, conversational, technical)
- Highlight unique value proposition for each role

### 3.4 — Supplementary Materials

- Portfolio project summaries matched to job requirements
- "Why this company" statement using AI-first signals from Phase 1
- Technical writing samples selection
- Reference to relevant blog posts or public work

### Deliverables
- [ ] Professional history knowledge base (seeded)
- [ ] Resume tailoring pipeline
- [ ] Cover letter generator
- [ ] Application package assembler (one command → all materials)
- [ ] Application tracking: `applications` table (job_id, date_applied, materials_generated, status, follow_ups)

---

## Phase 4: Professional Presence Automation

**Goal:** Keep LinkedIn, GitHub, and personal website continuously updated as a flywheel that feeds back into the job search.

**Timeline:** Ongoing, initial setup ~2 weeks

### 4.1 — Personal Website

- Static site (Hugo, Astro, or Next.js — whatever ships fastest)
- Sections:
  - About / Bio
  - Projects (auto-populated from projects database)
  - Blog (technical writing, AI implementation insights)
  - Resume (always-current, pulled from knowledge base)
  - Contact
- Auto-deploy from GitHub repo
- Design that reflects the AI-first philosophy (clean, functional, maybe even meta — "this site was built with AI assistance")

### 4.2 — GitHub Portfolio Curation

- Ensure key repos are public with excellent READMEs:
  - Beacon itself
  - Selected work projects (sanitized)
  - Technical blog post code companions
- Contribution graph strategy (consistent, meaningful commits)
- Pin best repos on profile
- GitHub profile README

### 4.3 — LinkedIn Automation

- Profile optimization:
  - Headline, about, experience aligned with target roles
  - Featured section with projects and blog posts
- Content strategy:
  - Share blog posts and project updates
  - Engage with AI-first company content
- Semi-automated posting (drafts generated, you review and post)
- Keep profile in sync with knowledge base updates

### 4.4 — Blog / Content Pipeline

- Topics derived from actual work:
  - "Building an AI-First Job Search Platform" (meta!)
  - Technical deep-dives on agentic workflows
  - Lessons from higher-ed AI implementation
  - Data engineering patterns with Databricks
- Cross-post to personal site + LinkedIn + Medium/Dev.to
- Each post becomes a portfolio artifact

### Deliverables
- [ ] Personal website deployed
- [ ] GitHub profile optimized with pinned repos
- [ ] LinkedIn profile updated and aligned
- [ ] Content calendar with 4-6 initial post ideas
- [ ] Automation scripts for cross-posting and sync

---

## Phase 5: Integration & Polish

**Goal:** Wire everything together into a cohesive, self-maintaining system.

**Timeline:** ~1-2 weeks

### 5.1 — Unified Dashboard

- Single view showing:
  - Company watchlist with scores and recent signals
  - Active job matches with application status
  - Professional presence health (site updated? GitHub active? LinkedIn current?)
  - Content pipeline status
- Could be a simple web app, CLI dashboard, or even a Notion/Obsidian integration

### 5.2 — Feedback Loops

- Track application outcomes → improve job matching
- Track which resume variants get responses → improve tailoring
- Track which blog posts get engagement → inform content strategy
- Company signals refresh on cadence

### 5.3 — Agent Orchestration

- This is where it gets meta: the entire system is an agentic workflow
- Claude Code / API integration for:
  - Company research updates
  - Job description analysis
  - Resume and cover letter generation
  - Blog post drafting
- Could evolve into a multi-agent system (researcher, writer, reviewer)

### Deliverables
- [ ] Integrated dashboard
- [ ] Feedback tracking
- [ ] Agent orchestration layer
- [ ] Documentation and architecture decision records

---

## Tech Stack (Recommended)

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Database | SQLite (via `sqlite3` or `sqlmodel`) | Zero infrastructure, portable, versioned with project |
| Language | Python 3.12+ | Your strength, fastest for data + AI work |
| CLI | `typer` or `click` | Professional CLI with minimal boilerplate |
| Web scraping | `httpx` + `beautifulsoup4`, `playwright` for JS-heavy pages | Covers API + scraping cases |
| LLM integration | Anthropic API (Claude) | Obvious choice, demonstrates platform familiarity |
| Personal site | Hugo or Astro | Fast static sites, Markdown-driven, free hosting |
| Hosting | GitHub Pages / Vercel / Cloudflare Pages | Free tier, auto-deploy |
| Scheduling | `cron` or GitHub Actions | Free, reliable, no infrastructure |
| Resume output | `weasyprint` or `python-docx` | PDF and DOCX from templates |
| Notifications | Email (SMTP) or Slack webhook | Simple, reliable |

---

## What Makes This Special

1. **It's the portfolio.** The system itself demonstrates agentic AI, data engineering, full-stack development, and strategic thinking — exactly what you'd be hired to do.

2. **Evidence-based targeting.** Instead of shotgunning applications, you're researching which companies actually live the AI-first culture. This is how a data scientist approaches job search.

3. **End-to-end automation.** From company discovery → job monitoring → application generation → professional presence maintenance. This is an agentic workflow that would make any AI-first company take notice.

4. **Self-reinforcing flywheel.** Every project you do feeds the website → feeds LinkedIn → feeds the resume → feeds the applications. The system gets stronger over time.

5. **Meta-recursive.** You're using AI tools to build a system that finds companies that value people who use AI tools. It's beautifully self-referential and demonstrates exactly the mindset these companies want.

---

## Open Questions to Resolve

- [ ] GitHub handle — needed for repo setup and profile optimization
- [ ] Existing domain / website — build new or migrate?
- [ ] Current resume — import and structure as baseline
- [ ] Budget tolerance ($0/mo vs $20-50/mo for hosting, API, domain)
- [ ] Timeline pressure — active search vs. building toward a move
- [ ] Privacy preferences — how much personal info on public site?
- [ ] Work project disclosure — what can be shared publicly (even sanitized) vs. what stays private?
- [ ] LinkedIn current state — needs overhaul or just refinement?
