# Beacon — AI-First Company Intelligence Database

## Agent Persona

Beacon is a **tool for the agent** — Claude Code is the intelligence layer. Beacon curates, scores, and monitors AI-first companies and their job listings. The agent synthesizes company data, scores, and job listings into actionable job-search guidance. No API key is required; the agent orchestrates beacon CLI commands on behalf of the user.

## Quick Start

```bash
# First-time setup (seeds 38 AI-first companies)
beacon init

# Run tests
.venv/bin/pytest tests/ -x -q

# Lint
.venv/bin/ruff check beacon/
```

## Project Structure

- **Framework:** Python 3.11+ CLI with Typer + Rich
- **Database:** SQLite via stdlib sqlite3 (`data/beacon.db`)
- **Schema:** `beacon/db/schema.sql` (CREATE IF NOT EXISTS pattern)
- **Entry point:** `beacon = "beacon.cli:main"` in `pyproject.toml`
- **Tests:** pytest with `tmp_path` fixtures, `@patch` for mocking
- **Lint:** ruff (line-length 120, per-file E501 ignores for seed/tests/formatters/cli)
- **Python binary:** `python3` (not `python`) on this system
- **pip:** requires `--break-system-packages` flag

## Convention: `--json` Flag

Every read/output command supports `--json`. When set:
- JSON goes to **stdout**, human-readable text to **stderr**
- Errors: `{"error": "...", "code": N}`
- Exit codes: `0` success, `1` error, `2` not found
- Prompts/confirmations are skipped

## Convention: Generated artifacts → Obsidian vault via `oj capture`

`beacon profile resume` and `beacon profile cover-letter` (and `beacon job apply
--generate`) write their markdown into the Obsidian vault by shelling out to
`oj capture`. Beacon never writes generated markdown to a local `output/`
directory — that pattern was retired in favor of the
"Obsidian-as-universal-output" project rule.

**Where artifacts land:**

```
$OBSIDIAN_VAULT_PATH/
  Job Search/
    Resumes/        {YYYY-MM-DD}-{company-slug}-resume.md
    Cover Letters/  {YYYY-MM-DD}-{company-slug}-cover-letter.md
    Applications/   (existing folder; cross-link via [[wikilinks]])
```

**Frontmatter contract** (always present):

```yaml
---
date: 2026-05-06
type: resume        # or cover-letter
company: "Anthropic"
role: "Forward Deployed Engineer"
source: beacon
tags: [job-search, beacon, generated, resume]   # `cover-letter` instead of `resume` for letters
---
```

**Finding artifacts from any agent:**

```bash
# Last cover letter for an AI-native company
oj query --tags job-search,cover-letter --json --limit 1

# All resumes ever written
oj query --folder "Job Search/Resumes" --json
```

**Overrides:**

- `beacon profile resume <id> --output PATH` — write to a local path instead of
  the vault (legacy escape hatch; PDF/DOCX always write locally because they're
  binary and `oj capture` is markdown-only).
- `beacon profile cover-letter <id> --output PATH` — same.

**Requires:** `oj` CLI on `$PATH` (from the `obsidian_journal` repo) and
`$OBSIDIAN_VAULT_PATH` set. If `oj` lives in a project-scoped venv instead of
on `$PATH`, set `OJ_BIN` to its absolute path:

```bash
export OJ_BIN=~/projects/obsidian_journal/.venv/bin/oj
```

`oj capture` itself does NOT require `ANTHROPIC_API_KEY` — it's a pure
file-write, no LLM round-trip.

## CLI Commands

### Root Commands

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon init [--seed]` | Initialize DB, optionally seed 38 companies | `--seed` (default true) |
| `beacon companies` | List companies by AI-first score | `--tier N` `--min-score N` `--tools TEXT` `--limit N` `--json` |
| `beacon show <name>` | Detailed company view (signals, tools, jobs) | `--json` |
| `beacon scores` | Recompute company scores. Bare command refreshes all; flags scope the recompute | `--since DAYS` `--company NAME` `--quiet` `--json` |
| `beacon stats` | Database statistics | `--json` |
| `beacon export <format>` | Export as markdown/csv/json/report | `--min-score N` `--output PATH` |
| `beacon scan` | Scan career pages for jobs | `--company TEXT` `--platform TEXT` `--min-score N` `--json` |
| `beacon jobs` | List job listings by relevance | `--company TEXT` `--status TEXT` `--min-relevance N` `--since DATE` `--new` `--limit N` `--json` |
| `beacon match-jobs` | Rank listings by overlap with the user's actual profile (skills + work history + outcomes) | `--limit N` `--min-fit FLOAT` `--status active\|all` `--explain` `--with-outcomes` `--json` |
| `beacon dashboard` | Unified dashboard | `--compact` `--json` |
| `beacon guide` | Onboarding guide | |

### Companies Sub-commands (`beacon companies ...`)

`beacon companies` with no subcommand still lists companies (legacy behavior).
The subcommands drive the pluggable discovery pipeline.

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon companies sources` | List registered discovery adapters with last-run + pending counts | `--json` |
| `beacon companies discover` | Fetch candidates from a source, dedupe, write to `discovery_candidates` | `--source NAME` `--limit N` `--dry-run` `--curated-dir PATH` (yaml only) `--json` |
| `beacon companies candidates` | List discovery candidates ranked by evidence-weighted score | `--source NAME` `--status pending\|promoted\|rejected\|all` `--limit N` `--json` |
| `beacon companies promote <id>` | Move a candidate into `companies` + copy signals into `ai_signals` | `--tier N` (default 4) `--json` |
| `beacon companies reject <id>` | Mark a candidate rejected so it isn't re-surfaced | `--reason TEXT` `--json` |
| `beacon companies diff` | Window diff of the company universe — new companies + role-count deltas | `--since DATE\|Nd\|last-week` `--tier N` `--min-score F` `--include-closed` `--limit N` `--json` |
| `beacon companies refresh-signals` | Re-fetch evidence for known companies (stalest-first) so recency scores don't silently rot | `--since DAYS` (default 90) `--company NAME` `--tier N` `--source NAME` `--limit N` (default 50) `--dry-run` `--json` |

**Sources in v0.1:**
- `yaml` — curated feed at `beacon/sources/curated/*.yml` (always available, no auth)
- `crunchbase` — Crunchbase v4 API; requires `CRUNCHBASE_API_KEY` env var; respects free-tier QPS with sleep + jitter

**Discovery scoring** (sort order for `candidates`): source weight + signal count (capped at 5) + 0.5 per filled field (domain/careers_url/industry/hq_location) + 1.0 bonus for any signal with strength ≥ 4. Implementation: `beacon/sources/dedupe.py:score_candidate`.

**Dedupe** (skipping policies): hard match on companies.name (case-insensitive), normalized name (alphanumerics-only) fuzzy match, exact domain match, AND a `UNIQUE(source, source_ref)` constraint so rejected candidates never re-surface.

### Job Sub-commands (`beacon job ...`)

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon job show <id>` | Detailed job info | `--json` |
| `beacon job apply <id>` | Mark as applied, create application record | `--generate` `--notes TEXT` |
| `beacon job ignore <id>` | Mark as ignored | |
| `beacon job add` | Manually add an external job listing (use `--fetch` to auto-extract from URL) | `--fetch` `--title TEXT` `--company TEXT` `--url TEXT` `--location TEXT` `--department TEXT` `--description TEXT` `--date-posted DATE` `--create-company` `--json` |

### Report Sub-commands (`beacon report ...`)

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon report digest` | Markdown digest of recent relevant jobs | `--since DATE` `--min-relevance N` `--output PATH` `--json` |
| `beacon report jobs` | Full markdown jobs report | `--output PATH` `--json` |
| `beacon report scoring-feedback` | Scoring calibration report | `--json` |
| `beacon report variant-effectiveness` | Resume variant effectiveness | `--json` |

### Profile Sub-commands (`beacon profile ...`)

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon profile show` | Profile summary | `--json` |
| `beacon profile work [ID]` | List/detail work experiences | `--json` |
| `beacon profile projects [ID]` | List/detail projects | `--json` |
| `beacon profile skills` | List skills by category | `--json` |
| `beacon profile education` | List education | `--json` |
| `beacon profile publications` | List publications/talks | `--json` |
| `beacon profile presentations` | List/detail presentations | `--detail ID` `--status TEXT` `--json` |
| `beacon profile speaker` | Speaker profile (bios, headshot) | `--json` |
| `beacon profile stats` | Profile completeness dashboard | `--json` |
| `beacon profile interview` | Interactive profile interview | `--section TEXT` |
| `beacon profile import <file>` | Import profile from JSON | |
| `beacon profile export` | Export profile as JSON | `--output PATH` |
| `beacon profile resume <job_id>` | Generate tailored resume (markdown lands in vault via `oj capture`) | `--pages N` `--format TEXT` `--output PATH` `--json` |
| `beacon profile cover-letter <job_id>` | Generate cover letter (lands in vault via `oj capture`) | `--tone TEXT` `--output PATH` `--json` |
| `beacon profile add-presentation` | Add a presentation | `--title TEXT` `--event TEXT` `--date DATE` `--status TEXT` ... |
| `beacon profile set-headshot <path>` | Set headshot image path | |

### Materials Sub-commands (`beacon materials ...`)

Pre-application + application-time artifacts. `resume` and `cover-letter` are
still exposed under `beacon profile ...` for backward compatibility; the
`materials` group is the canonical surface for new commands.

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon materials interview-brief` | Generate one vault-resident interview prep brief per top-N job match. Joins `match-jobs` rows with company research, skill gaps, optional `stack-quest arcs suggest` arc, and profile talking points. Writes to `$OBSIDIAN_VAULT_PATH/Job Search/interview-briefs/`. | `--top N` (default 5) `--min-fit FLOAT` (default 6.0) `--with-outcomes/--no-with-outcomes` `--vault/--no-vault` `--dry-run` `--json` |

The brief is deterministic — no LLM calls in v1. Each note renders 8 sections:
Snapshot, Why this matches (fit reasoning + sub-scores), Company posture
(leadership/AI signals/tools from Phase 1 research), Gap analysis (missing
skills × `beacon gaps list`), Suggested next move (stack-quest arc that closes
a missing skill), Talking points (work/projects ranked by skill overlap),
Prep questions (role-family-templated + dynamic from leadership signals),
Application checklist.

### Application Sub-commands (`beacon application ...`)

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon application list` | List applications | `--status TEXT` `--json` |
| `beacon application show <id>` | Application detail | `--json` |
| `beacon application update <id>` | Update status/notes | `--status TEXT` `--notes TEXT` |
| `beacon application outcome <id>` | Record outcome | `--outcome TEXT` `--days N` `--notes TEXT` |
| `beacon application outcomes` | List outcomes | `--outcome TEXT` `--json` |
| `beacon application effectiveness` | Outcome/variant analysis | `--json` |

### Presence Sub-commands (`beacon presence ...`)

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon presence drafts` | List content drafts | `--platform TEXT` `--status TEXT` `--json` |
| `beacon presence draft <id>` | View a draft | `--json` |
| `beacon presence publish <id>` | Mark draft as published | `--url TEXT` |
| `beacon presence calendar` | List calendar entries | `--platform TEXT` `--status TEXT` `--json` |
| `beacon presence calendar-add` | Add calendar entry | `--title TEXT` `--platform TEXT` `--type TEXT` `--date DATE` |
| `beacon presence calendar-seed` | Auto-generate calendar ideas (LLM) | |
| `beacon presence github` | Generate GitHub README (LLM) | `--output PATH` |
| `beacon presence linkedin-headline` | Generate LinkedIn headlines (LLM) | |
| `beacon presence linkedin-about` | Generate LinkedIn About (LLM) | |
| `beacon presence linkedin-post` | Generate LinkedIn post (LLM) | `--topic TEXT` `--tone TEXT` |
| `beacon presence blog-outline` | Generate blog outline (LLM) | `--topic TEXT` |
| `beacon presence blog-generate` | Generate full blog post (LLM) | `--topic TEXT` `--output PATH` |
| `beacon presence blog-export <id>` | Export blog for platform | `--format TEXT` `--output PATH` |
| `beacon presence bio` | Generate speaker bio (LLM) | `--length TEXT` `--save` `--output PATH` |
| `beacon presence site-generate` | Generate Astro site content | `--output PATH` |
| `beacon presence site-resume` | Generate resume page | `--output PATH` |
| `beacon presence site-projects` | Generate project pages | `--output PATH` |
| `beacon presence enrich` | Enrichment interview / gap analysis | `--work-id N` `--list-gaps` `--generate-content` |

### Media Sub-commands (`beacon media ...`)

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon media add <title>` | Log a video, podcast, article, etc. | `--type TEXT` `--url TEXT` `--creator TEXT` `--platform TEXT` `--date DATE` `--rating N` `--tag TEXT` `--takeaways TEXT` `--reaction TEXT` `--shareable` `--share-note TEXT` `--why TEXT` `--quote TEXT` `--category TEXT` `--json` |
| `beacon media list` | List media entries with filters | `--type TEXT` `--tag TEXT` `--min-rating N` `--since DATE` `--search TEXT` `--limit N` `--json` |
| `beacon media show <id>` | Show media entry detail | `--json` |
| `beacon media update <id>` | Update fields on a media entry | `--takeaways TEXT` `--reaction TEXT` `--rating N` `--shareable` `--share-note TEXT` `--why TEXT` `--quote TEXT` `--category TEXT` `--tag TEXT` `--json` |
| `beacon media team-list` | Export team-shareable media as markdown/JSON | `--type TEXT` `--tag TEXT` `--min-rating N` `--since DATE` `--limit N` `--output PATH` `--json` |
| `beacon media export-list` | Export for Microsoft Lists / Power Automate | `--type TEXT` `--tag TEXT` `--min-rating N` `--since DATE` `--category TEXT` `--limit N` `--format TEXT` `--output PATH` `--json` |

### Network Sub-commands (`beacon network ...`)

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon network add-event <name>` | Log a networking event | `--organizer TEXT` `--type TEXT` `--url TEXT` `--location TEXT` `--date DATE` `--status TEXT` `--tag TEXT` `--json` |
| `beacon network events` | List events with filters | `--status TEXT` `--type TEXT` `--since DATE` `--search TEXT` `--limit N` `--json` |
| `beacon network event <id>` | Show event detail + contacts | `--json` |
| `beacon network add-contact <name>` | Add a professional contact | `--title TEXT` `--company TEXT` `--email TEXT` `--linkedin TEXT` `--interest TEXT` `--priority N` `--event N` `--json` |
| `beacon network contacts` | List contacts with filters | `--company TEXT` `--event N` `--min-priority N` `--search TEXT` `--limit N` `--json` |
| `beacon network contact <id>` | Show contact detail + event history | `--json` |
| `beacon network link <contact_id> <event_id>` | Link contact to event | `--topics TEXT` `--follow-up TEXT` `--notes TEXT` `--json` |
| `beacon network prep <event_id>` | Prep for event: contacts, beacon cross-refs | `--json` |

### Config Sub-commands (`beacon config ...`)

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon config show` | Show current configuration | `--json` |
| `beacon config set <key> <value>` | Set a config value | |
| `beacon config init` | Create default config file | |

### Automation Sub-commands (`beacon automation ...`)

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon automation run` | Run automation cycle | `--scan-only` `--digest-only` |
| `beacon automation log` | Show run history | `--limit N` `--json` |
| `beacon automation cron <action>` | Manage cron scheduling | `--every N` |
| `beacon automation agents` | Run all automation agents | `--dry-run` |
| `beacon automation agents-status` | Recent agent run summaries | `--json` |
| `beacon automation test-notify` | Send test notification | |

### Gaps Sub-commands (`beacon gaps ...`)

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon gaps analyze` | Analyze gaps against top jobs and persist | `--min-relevance N` `--location TEXT` `--limit N` `--json` |
| `beacon gaps list` | List tracked gaps (versioned envelope contract — see below) | `--status TEXT` `--category TEXT` `--min-demand N` `--limit N` `--sort {demand,priority,recent}` `--legacy-array` `--json` |
| `beacon gaps update <skill>` | Update a gap's status (open / learning / closed) | `--status TEXT` |
| `beacon gaps export` | Export open gaps as quest-ready dicts for code-daily | `--limit N` `--json` |

**`gaps list` vs `gaps export` — when to use which:**
- `gaps list` is the canonical read API. Use it for any analytical, dashboard, or filtering use case (consumed by stack-quest's `arcs suggest`).
- `gaps export` is a one-way transformation that wraps open gaps in a quest envelope (title / source / source_ref / description). Use it only when feeding code-daily's quest queue.

### Gaps subcommand contract

`beacon gaps list --json` emits a versioned envelope. Downstream agents (stack-quest, code-daily) should read this contract before consuming the output.

**Envelope:**

```json
{
  "schema_version": 1,
  "gaps": [ /* gap objects */ ]
}
```

**Gap object fields** (every field is always present — `null` when unknown):

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Primary key |
| `skill_name` | string | Canonical skill name (post-normalization) |
| `category` | string \| null | `language`, `framework`, `tool`, `domain`, or `other` |
| `demand_count` | int | Number of analyzed jobs requiring this skill |
| `example_jobs` | array | `[{id, title, company}, ...]`, max 3 per gap |
| `status` | string | `open`, `learning`, or `closed` |
| `priority` | int | Defaults to `demand_count` at insert |
| `created_at` | string | SQLite `datetime('now')` |
| `updated_at` | string | SQLite `datetime('now')`, refreshed on upsert |

**Filters** (compose with AND, all execute server-side in SQL):
- `--status open|learning|closed`
- `--category TEXT` (repeatable — matches any of)
- `--min-demand INT`
- `--limit INT`
- `--sort demand|priority|recent` (default `demand`)

**Sort definitions:**
- `demand` → `demand_count DESC, priority DESC, skill_name ASC`
- `priority` → `priority DESC, demand_count DESC, skill_name ASC`
- `recent` → `updated_at DESC, demand_count DESC, skill_name ASC`

**Errors / exit codes:**
- `0` success
- `1` invalid input (e.g. unknown `--sort`); JSON body: `{"error": "...", "code": 1}`

**Backward compatibility:**
- `--legacy-array` returns the bare pre-v1 array (no envelope). Slated for removal once stack-quest migrates — do not adopt in new integrations.

Contract stability is enforced by `tests/test_gaps_contract.py`. Any change to envelope shape, gap fields, filter semantics, or sort defaults must bump `schema_version` and update consumers.

### Session Sub-commands (`beacon session ...`)

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon session log <title>` | Log a Claude Code session | `--summary TEXT` `--tag TEXT` `--tech TEXT` `--impact TEXT` `--project TEXT` `--json` |
| `beacon session list` | List sessions | `--project TEXT` `--tag TEXT` `--limit N` `--json` |
| `beacon session show <id>` | Show session detail | `--json` |

## Agent Usage Examples

```bash
# Get all tier-1 companies as JSON for cross-project use
beacon companies --tier 1 --json

# Discover new AI-first companies from the curated YAML feed (no auth)
beacon companies discover --source yaml --json | jq '.inserted'

# Discover from Crunchbase (requires CRUNCHBASE_API_KEY env var)
beacon companies discover --source crunchbase --limit 25 --json

# Review evidence-ranked pending candidates, then promote the strongest
beacon companies candidates --status pending --json | jq '.[0:5]'
beacon companies promote 7 --tier 3 --json
beacon companies reject 8 --reason "not actually AI-native" --json

# Refresh evidence for companies whose newest signal is >90 days old
beacon companies refresh-signals --since 90 --limit 25 --json | jq '.totals'
# Targeted: refresh just one company
beacon companies refresh-signals --company "Anthropic" --json
# After a refresh, recompute scores for any company whose data has shifted
beacon scores --since 7 --json | jq '.recomputed'

# Find relevant jobs at a specific company
beacon jobs --company "Anthropic" --min-relevance 7 --json

# Rank known listings by overlap with the user's actual profile (not just static keywords)
beacon match-jobs --limit 10 --json
# Layer in empirical lift from skills that have produced positive outcomes
beacon match-jobs --with-outcomes --min-fit 6 --json

# Get full company intel for synthesis
beacon show "Vercel" --json

# Dashboard data for briefing generation
beacon dashboard --json

# Recent job scan results
beacon jobs --since 2024-01-01 --min-relevance 8 --json

# Application pipeline status
beacon application list --status applied --json

# Profile data for resume generation
beacon profile show --json

# Tailor a resume for a job — lands in $OBSIDIAN_VAULT_PATH/Job Search/Resumes/
beacon profile resume 42 --json
# {"path": "Job Search/Resumes/2026-05-06-anthropic-resume.md", ...}

# Same for a cover letter
beacon profile cover-letter 42 --json

# Look up the most recent generated artifact from any other agent / project
oj query --tags job-search,cover-letter --json --limit 1

# Log a video you watched with reaction and sharing fields
beacon media add "Andrej Karpathy - Intro to LLMs" --type video --creator "Andrej Karpathy" --platform YouTube --rating 5 --tag ai --tag llm --reaction "Great mental model for how LLMs work" --shareable --share-note "Best intro to LLMs for non-technical folks" --why "Gives the team a shared mental model for how LLMs actually work" --quote "The LLM is dreaming the next token" --category "AI Adoption" --json

# Get team-shareable media list for AI adoption
beacon media team-list --min-rating 4 --json

# Export for Microsoft Lists / Power Automate (JSON or CSV)
beacon media export-list --format csv --output export.csv
beacon media export-list --category "AI Adoption" --json

# Search your media log
beacon media list --search "agents" --type video --json

# Log a networking event
beacon network add-event "AI Tinkerers Columbus" --organizer "AI Tinkerers" --date 2026-04-15 --location "Columbus, OH" --status attended --json

# Add a contact met at an event
beacon network add-contact "Jane Smith" --title "ML Engineer" --company "Anthropic" --event 1 --priority 4 --interest "agents" --json

# Prep for an upcoming event (cross-references beacon companies)
beacon network prep 1 --json

# List contacts at a specific event
beacon network contacts --event 1 --json
```

## Structured Filtering

Read commands support composable filters (AND logic):

- `beacon companies --min-score 7 --tier 1 --tools "cursor"` — tier-1 companies scoring 7+ that use Cursor
- `beacon jobs --min-relevance 8 --status active --company "Vercel" --since 2024-01-01` — high-relevance active jobs at Vercel since a date
- `beacon media list --type video --min-rating 4 --tag "agents" --since 2026-01-01` — high-rated agent videos since a date
- `beacon network contacts --company "Anthropic" --min-priority 3 --event 1` — high-priority Anthropic contacts from event 1
- `beacon network events --status upcoming --type meetup --since 2026-04-01` — upcoming meetups since a date

## Database

- SQLite at `data/beacon.db`
- Schema in `beacon/db/schema.sql`
- Key tables: `companies`, `ai_signals`, `leadership_signals`, `tools_adopted`, `score_breakdown`, `job_listings`, `applications`, `application_outcomes`, `work_experiences`, `projects`, `skills`, `education`, `publications_talks`, `content_drafts`, `content_calendar`, `media_log`, `network_events`, `network_contacts`, `network_contact_events`, `presentations`, `speaker_profile`, `resume_variants`, `automation_log`, `sessions`, `discovery_candidates`
- `beacon init` must be run before first use (creates schema + seeds 38 companies)

## Environment Variables

In addition to the global env vars in `~/.bashrc`:

- `CRUNCHBASE_API_KEY` — Crunchbase v4 API bearer key. Required only for `beacon companies discover --source crunchbase`; missing key returns `{"error": "CRUNCHBASE_API_KEY unset", "code": 1}` and exits 1.

## Optional Dependencies

- `pip install beacon[scraping]` — httpx + beautifulsoup4 for job scanning
- `pip install beacon[llm]` — anthropic SDK for content generation
- `pip install beacon[docs]` — python-docx + fpdf2 for resume rendering
- `pip install beacon[notifications]` — plyer for desktop notifications

## Web UI (`web/`)

Next.js 15 + Tailwind + TypeScript dashboard at `web/`. Read-only view over `data/beacon.db` via `better-sqlite3`, falls back to mock data when the DB is missing or empty. All routes ship with real data:

- `/dashboard` — A/B/C direction toggle (Command Deck / Briefing / Console).
- `/applications` — kanban ↔ list toggle over the `applications` pipeline.
- `/jobs` — card variation picker over `job_listings`.
- `/companies` — sortable/filterable table over `companies` + tier/score/tool chips. When `discovery_candidates` has pending rows, a collapsible **Discovery rail** renders above the filter bar with per-source pending counts and copy-to-clipboard `beacon companies promote/reject` CLI chips. The rail is hidden entirely when nothing is pending.
- `/content` — calendar strip + drafts kanban + staleness alerts + resume-variant freshness, plus a **Presentations** row driven by the `presentations` table and a **Presence quick-actions** grid of CLI chips (linkedin-post, blog-outline, site-generate, bio, etc.). Empty presentations state shows a single `beacon profile add-presentation` chip.
- `/settings` — real reads: scoring weights come from `beacon/research/scoring.py` constants with an `isCodeDefined` tag (edits live in code, not `beacon config`); automation pulls live from `automation_log`; notifications hydrate from `data/beacon.toml` (path overridable via `BEACON_CONFIG`). When the toml is missing, BeaconConfig defaults render and the page still shows `isMockData: false`.

```bash
cd web && npm install
npm run dev       # http://localhost:3000
npm run build     # production build
npm test          # vitest unit tests for data/config layer
```

The dashboard direction + pipeline view + theme all persist per-user via localStorage keys (`beacon-theme`, `beacon-direction`, `beacon-pipeline-view`). Pages are server-rendered (`dynamic = "force-dynamic"`) so DB changes are picked up on each request.

**Data flow:** `web/lib/data.ts` is the only place that reads `data/beacon.db`. Each route page calls a `load*Data()` function which returns the page's view-model type from `web/lib/types.ts`. Views in `web/app/(app)/<route>/view.tsx` are pure renderers of that view-model — no DB access. When the DB is missing or empty, the loaders return the shapes in `web/lib/mock-data.ts` so the screen-share demo path still works.
