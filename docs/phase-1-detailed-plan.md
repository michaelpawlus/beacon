# Phase 1: Company Intelligence Database — Detailed Plan

## Overview

Build a curated, evidence-backed database of AI-first companies. This is the foundation of the entire Beacon platform and also a standalone portfolio piece — publishable as a blog post, shareable as a dataset, and demonstrative of research + data engineering skills.

---

## Week 1: Schema, Tooling & Initial Research

### Day 1–2: Project Setup & Database Schema

**Repository initialization:**
```
beacon/
├── README.md                  # Project overview, architecture, philosophy
├── pyproject.toml             # Project config (uv or poetry)
├── beacon/
│   ├── __init__.py
│   ├── cli.py                 # Typer CLI entrypoint
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py          # SQLModel or dataclass definitions
│   │   ├── schema.sql         # Raw SQL schema (for reference)
│   │   └── seed.py            # Seeding script
│   ├── research/
│   │   ├── __init__.py
│   │   ├── signals.py         # Signal collection helpers
│   │   └── scoring.py         # Composite score computation
│   └── export/
│       ├── __init__.py
│       └── formatters.py      # JSON, CSV, Markdown export
├── data/
│   ├── beacon.db              # SQLite database (gitignored)
│   └── seed_companies.json    # Initial company data (committed)
├── docs/
│   └── schema.md              # Schema documentation
└── tests/
    └── test_scoring.py
```

**SQLite Schema:**

```sql
-- Core company information
CREATE TABLE companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    domain TEXT,                          -- e.g., "anthropic.com"
    careers_url TEXT,                     -- direct link to careers/jobs page
    careers_platform TEXT,                -- greenhouse, lever, ashby, workday, custom
    hq_location TEXT,
    remote_policy TEXT CHECK(remote_policy IN ('remote-first', 'hybrid', 'onsite', 'flexible', 'unknown')),
    size_bucket TEXT CHECK(size_bucket IN ('startup-<50', 'small-50-200', 'mid-200-1000', 'large-1000-5000', 'enterprise-5000+')),
    industry TEXT,
    founded_year INTEGER,
    description TEXT,
    ai_first_score REAL DEFAULT 0,       -- composite score (0-10)
    tier INTEGER DEFAULT 4,              -- 1=AI-native, 2=AI-first convert, 3=strong adoption, 4=emerging
    last_researched_at TEXT,             -- ISO datetime
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Evidence of AI-first culture
CREATE TABLE ai_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    signal_type TEXT NOT NULL CHECK(signal_type IN (
        'leadership_statement',      -- CEO/CTO public quote or policy
        'engineering_blog',          -- Blog post about AI workflows
        'job_posting_language',      -- Job listings requiring/encouraging AI tools
        'conference_talk',           -- Talks/podcasts about AI adoption
        'employee_report',           -- Glassdoor, Blind, Reddit, X posts
        'press_coverage',            -- News articles about AI initiatives
        'github_activity',           -- Public repos showing AI tool usage
        'company_policy',            -- Official AI usage policies
        'product_integration',       -- AI integrated into their product
        'tool_mandate'               -- Explicit mandates (like Shopify's)
    )),
    title TEXT NOT NULL,                 -- Brief description of the signal
    source_url TEXT,
    source_name TEXT,                    -- "TechCrunch", "Company Blog", "X/Twitter", etc.
    excerpt TEXT,                        -- Key quote or summary
    signal_strength INTEGER CHECK(signal_strength BETWEEN 1 AND 5),  -- 1=weak, 5=definitive
    date_observed TEXT,                  -- When the signal was published/observed
    verified BOOLEAN DEFAULT FALSE,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Specific leadership buy-in evidence
CREATE TABLE leadership_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    leader_name TEXT NOT NULL,
    leader_title TEXT,
    signal_type TEXT CHECK(signal_type IN ('quote', 'policy', 'memo', 'talk', 'tweet', 'interview')),
    content TEXT NOT NULL,               -- The actual quote or policy description
    source_url TEXT,
    date_observed TEXT,
    impact_level TEXT CHECK(impact_level IN ('company-wide', 'engineering', 'team', 'personal')),
    created_at TEXT DEFAULT (datetime('now'))
);

-- AI tools explicitly adopted/encouraged
CREATE TABLE tools_adopted (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    tool_name TEXT NOT NULL,             -- Claude Code, GitHub Copilot, Cursor, Codex, etc.
    adoption_level TEXT CHECK(adoption_level IN ('required', 'encouraged', 'allowed', 'exploring', 'rumored')),
    evidence_url TEXT,
    evidence_excerpt TEXT,
    date_observed TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Computed/cached scoring breakdown
CREATE TABLE score_breakdown (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id) UNIQUE,
    leadership_score REAL DEFAULT 0,     -- 0-10: How bought-in is leadership?
    tool_adoption_score REAL DEFAULT 0,  -- 0-10: How many AI tools, how deeply adopted?
    culture_score REAL DEFAULT 0,        -- 0-10: Is AI-first in the DNA, not just a pilot?
    evidence_depth_score REAL DEFAULT 0, -- 0-10: How much evidence do we have?
    recency_score REAL DEFAULT 0,        -- 0-10: How recent are the signals?
    composite_score REAL DEFAULT 0,      -- Weighted average
    last_computed_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Index for common queries
CREATE INDEX idx_companies_score ON companies(ai_first_score DESC);
CREATE INDEX idx_companies_tier ON companies(tier);
CREATE INDEX idx_signals_company ON ai_signals(company_id);
CREATE INDEX idx_signals_type ON ai_signals(signal_type);
CREATE INDEX idx_leadership_company ON leadership_signals(company_id);
CREATE INDEX idx_tools_company ON tools_adopted(company_id);
```

### Day 2–3: Scoring Algorithm

**Composite scoring formula:**

```
composite = (
    leadership_score    * 0.30 +    # Leadership buy-in is the #1 signal
    tool_adoption_score * 0.25 +    # Actual tool usage matters
    culture_score       * 0.25 +    # Is it in the DNA?
    evidence_depth      * 0.10 +    # More evidence = more confidence
    recency_score       * 0.10      # Recent signals > old ones
)
```

**Sub-score computation:**

| Sub-score | Inputs | Logic |
|-----------|--------|-------|
| Leadership | leadership_signals count, impact_level, leader seniority | CEO-level company-wide mandate = 10, team-level exploration = 3 |
| Tool Adoption | tools_adopted count, adoption_level | Multiple tools at "required" level = 10, one tool "exploring" = 2 |
| Culture | signals of type employee_report, engineering_blog, job_posting_language | Multiple consistent signals = high, single anecdote = low |
| Evidence Depth | Total signal count across all tables | Logarithmic scale (diminishing returns after ~15 signals) |
| Recency | Average age of signals, most recent signal date | Signals from last 3 months = 10, >1 year old = decayed |

### Day 3–5: Initial Company Research & Seeding

**Research methodology per company:**

1. Search for `"[company] AI tools engineering"` and `"[company] CEO AI"`
2. Check their engineering blog for AI-related posts
3. Review recent job postings for AI tool mentions
4. Check X/Twitter for leadership statements
5. Search Hacker News, Reddit for employee perspectives
6. Review Glassdoor for AI culture mentions

**Initial target list (to research and score):**

#### Tier 1 — AI-Native Companies
These companies build AI tools or were founded on AI-first principles.

| Company | Why investigate |
|---------|----------------|
| Anthropic | Claude makers — obviously AI-first |
| OpenAI | Competitive but clearly AI-native |
| Cursor | AI-first code editor company |
| Cognition (Devin) | AI software engineering |
| Replit | AI-powered development platform |
| Vercel | v0 and AI integration focus |
| Hugging Face | Open-source AI infrastructure |
| Cohere | Enterprise AI platform |
| Mistral | AI model company |
| Perplexity | AI search |
| Anysphere | Cursor parent company |

#### Tier 2 — AI-First Converts (Leadership Mandates)
These companies have made public, leadership-driven shifts to AI-first operations.

| Company | Key Signal |
|---------|------------|
| Shopify | Tobi Lütke's memo: AI usage required before hiring |
| Klarna | Replaced hundreds of roles with AI, CEO very public |
| Duolingo | AI-first content generation, reduced contractors |
| Mercado Libre | Major AI investment, Latin America's Amazon going AI-first |
| Block (Square) | Jack Dorsey pushing AI-first engineering |
| Fiverr | CEO publicly embraced AI transformation |

#### Tier 3 — Strong AI Adoption
Significant AI integration in engineering culture, even if not "mandated."

| Company | Why investigate |
|---------|----------------|
| Stripe | Known for AI in code review, internal tools |
| Netflix | ML/AI deeply embedded in engineering culture |
| Spotify | AI-first recommendations, Wrapped, etc. |
| Databricks | AI/ML infrastructure company |
| Snowflake | Competing hard on AI features |
| Palantir | AI platform company, strong AI culture |
| Meta | Heavy AI investment, LLaMA |
| Google DeepMind | Pure AI research + application |
| Amazon (AWS AI) | Bedrock, heavy AI investment |
| Notion | AI features, likely internal AI adoption |
| Linear | Small but known for AI-augmented development |
| GitLab | AI features, remote-first |
| Figma | AI design tools |
| Canva | Major AI investment |

#### Tier 4 — Emerging Signals (Need More Research)
Companies with some AI signals that need deeper investigation.

| Company | Signal to investigate |
|---------|----------------------|
| Airbnb | Engineering culture + AI features |
| Uber | ML-heavy operations |
| DoorDash | Data-driven, AI logistics |
| Ramp | AI-first finance |
| Brex | AI-first finance |
| Scale AI | AI training data company |
| Weights & Biases | ML tooling company |
| dbt Labs | Data tooling, AI features |
| Hex | Data platform with AI |
| Modal | AI infrastructure |
| Together AI | AI inference infrastructure |
| Groq | AI hardware/inference |
| Coda | AI workplace tools |

---

## Week 2: CLI, Exports & Polish

### Day 6–7: CLI Interface

```bash
# Company management
beacon companies list                          # All companies, sorted by score
beacon companies list --tier 1 --min-score 8   # Filtered
beacon companies show "Shopify"                # Full detail with all signals
beacon companies add --interactive             # Guided add

# Signal management
beacon signals add --company "Shopify" --type leadership_statement \
  --title "Tobi's AI Mandate" \
  --url "https://..." \
  --excerpt "Before asking for more headcount..." \
  --strength 5

beacon signals list --company "Shopify"        # All signals for a company

# Scoring
beacon scores refresh                          # Recompute all scores
beacon scores refresh --company "Shopify"      # Single company

# Exports
beacon export markdown                         # Markdown table of all companies
beacon export json --min-score 7               # JSON for downstream use
beacon export csv                              # CSV for analysis
beacon export report                           # Full markdown report (blog-ready)

# Research helper
beacon research suggest                        # Suggest companies needing more signals
beacon research stale                          # Companies not researched in 30+ days
```

### Day 8–9: Export & Blog-Ready Report

Generate a publishable markdown report:

```markdown
# The AI-First Company Index (2025)

A curated, evidence-backed ranking of companies where AI tools aren't just
allowed — they're expected. Every entry includes public evidence of leadership
buy-in, tool adoption, and cultural integration.

## Methodology
[Explain scoring system]

## Tier 1: AI-Native
[Company cards with scores and key evidence]

## Tier 2: AI-First Converts
...
```

This report serves triple duty:
1. Blog post for personal site
2. LinkedIn article for visibility
3. Demonstrates research + data skills to potential employers

### Day 10: Documentation & Ship

- Polish README with:
  - Clear problem statement
  - Architecture diagram
  - Setup instructions
  - Screenshots/examples of CLI output
  - Link to published report
- Write CONTRIBUTING.md (signals contributions model)
- Tag v0.1.0 release
- Push to public GitHub

---

## Definition of Done — Phase 1

- [ ] SQLite database with complete schema and all indexes
- [ ] 30+ companies researched and scored with real evidence
- [ ] At least 100 total signals across all companies
- [ ] Every Tier 1 and Tier 2 company has 3+ signals
- [ ] Scoring algorithm implemented and tested
- [ ] CLI with all core commands working
- [ ] Export to Markdown, JSON, CSV
- [ ] Blog-ready report generated
- [ ] Public GitHub repo with professional README
- [ ] All evidence URLs are real and verified
- [ ] Code is clean, typed, and has basic tests

---

## What This Demonstrates to Employers

| Skill | How Phase 1 Shows It |
|-------|---------------------|
| Data Engineering | Schema design, SQLite, data modeling, scoring algorithms |
| Research & Analysis | Systematic evidence gathering, multi-source synthesis |
| AI/ML Thinking | Building a scoring model, signal weighting, evidence-based ranking |
| Software Engineering | Clean Python, CLI tools, project structure, testing |
| Strategic Thinking | Approaching job search as a data problem |
| Communication | Published report, clear documentation |
| Shipping | Functional v0.1 in ~2 weeks |

---

## Transition to Phase 2

Once the company database is populated, Phase 2 (Job Scanner) builds directly on it:
- `companies.careers_url` → scanner knows where to look
- `companies.careers_platform` → scanner knows which adapter to use
- `companies.ai_first_score` → scanner prioritizes high-score companies
- `companies.remote_policy` → scanner filters by your preferences

The foundation is everything.
