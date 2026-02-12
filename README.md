# Beacon 🔦

**AI-First Company Intelligence Database**

A curated, evidence-backed database of companies where AI tools aren't just allowed — they're expected. Every entry includes public evidence of leadership buy-in, tool adoption, and cultural integration.

> Most job boards tell you *who's hiring*. Beacon tells you *who's building the future*.

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
# Clone and install
git clone https://github.com/michaelpawlus/beacon.git
cd beacon
pip install -e .

# Initialize database with seed data (25+ companies)
beacon init

# List all companies by AI-first score
beacon companies

# Show detailed info for a company
beacon show Shopify

# Export as markdown
beacon export markdown

# Export as CSV or JSON
beacon export csv --output companies.csv
beacon export json --min-score 7
```

## Current Data

The seed dataset includes 25+ companies across four tiers:

| Tier | Description | Example Companies |
|------|-------------|-------------------|
| 🟢 Tier 1 | AI-Native | Anthropic, Cursor, Vercel, Replit, Databricks |
| 🔵 Tier 2 | AI-First Converts | Shopify (Tobi's mandate), Klarna, Duolingo |
| 🟡 Tier 3 | Strong Adoption | Stripe, Notion, GitLab, Ramp, Scale AI |
| ⚪ Tier 4 | Emerging Signals | *(research in progress)* |

## Scoring

The composite score (0–10) is computed from verifiable public signals:

```
Composite = Leadership × 0.30 + Tools × 0.25 + Culture × 0.25 + Evidence × 0.10 + Recency × 0.10
```

Run `beacon show <company>` to see the full breakdown for any company.

## Project Roadmap

Beacon is the foundation for a larger job search automation platform:

- [x] **Phase 1:** Company Intelligence Database (this repo)
- [ ] **Phase 2:** Job Scanner — monitor career pages on target companies
- [ ] **Phase 3:** Application Generator — auto-generate tailored resumes and cover letters
- [ ] **Phase 4:** Professional Presence — website, GitHub, LinkedIn automation

## Contributing Signals

Know about a company's AI adoption that isn't in the database? Contributions welcome:

1. Open an issue with the company name and evidence URL
2. Or submit a PR adding to `beacon/db/seed.py`

Every signal needs a public, verifiable source (blog post, tweet, news article, job posting).

## Tech Stack

- **Python 3.11+** with type hints
- **SQLite** — zero infrastructure, portable, version-controllable
- **Typer + Rich** — professional CLI with beautiful output
- **No external APIs required** — the database is the product

## License

MIT
