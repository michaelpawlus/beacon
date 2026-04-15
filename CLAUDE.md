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

## CLI Commands

### Root Commands

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon init [--seed]` | Initialize DB, optionally seed 38 companies | `--seed` (default true) |
| `beacon companies` | List companies by AI-first score | `--tier N` `--min-score N` `--tools TEXT` `--limit N` `--json` |
| `beacon show <name>` | Detailed company view (signals, tools, jobs) | `--json` |
| `beacon scores` | Recompute all company scores | |
| `beacon stats` | Database statistics | `--json` |
| `beacon export <format>` | Export as markdown/csv/json/report | `--min-score N` `--output PATH` |
| `beacon scan` | Scan career pages for jobs | `--company TEXT` `--platform TEXT` `--min-score N` `--json` |
| `beacon jobs` | List job listings by relevance | `--company TEXT` `--status TEXT` `--min-relevance N` `--since DATE` `--new` `--limit N` `--json` |
| `beacon dashboard` | Unified dashboard | `--compact` `--json` |
| `beacon guide` | Onboarding guide | |

### Job Sub-commands (`beacon job ...`)

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `beacon job show <id>` | Detailed job info | `--json` |
| `beacon job apply <id>` | Mark as applied, create application record | `--generate` `--notes TEXT` |
| `beacon job ignore <id>` | Mark as ignored | |
| `beacon job add` | Manually add an external job listing | `--title TEXT` `--company TEXT` `--url TEXT` `--location TEXT` `--department TEXT` `--description TEXT` `--date-posted DATE` `--create-company` `--json` |

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
| `beacon profile resume <job_id>` | Generate tailored resume | `--pages N` `--format TEXT` `--output PATH` |
| `beacon profile cover-letter <job_id>` | Generate cover letter | `--tone TEXT` `--output PATH` |
| `beacon profile add-presentation` | Add a presentation | `--title TEXT` `--event TEXT` `--date DATE` `--status TEXT` ... |
| `beacon profile set-headshot <path>` | Set headshot image path | |

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

# Find relevant jobs at a specific company
beacon jobs --company "Anthropic" --min-relevance 7 --json

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
- Key tables: `companies`, `ai_signals`, `leadership_signals`, `tools_adopted`, `score_breakdown`, `job_listings`, `applications`, `application_outcomes`, `work_experiences`, `projects`, `skills`, `education`, `publications_talks`, `content_drafts`, `content_calendar`, `media_log`, `network_events`, `network_contacts`, `network_contact_events`, `presentations`, `speaker_profile`, `resume_variants`, `automation_log`, `sessions`
- `beacon init` must be run before first use (creates schema + seeds 38 companies)

## Optional Dependencies

- `pip install beacon[scraping]` — httpx + beautifulsoup4 for job scanning
- `pip install beacon[llm]` — anthropic SDK for content generation
- `pip install beacon[docs]` — python-docx + fpdf2 for resume rendering
- `pip install beacon[notifications]` — plyer for desktop notifications
