# Beacon Onboarding Guide

A step-by-step walkthrough to get up and running with Beacon.

## 1. Install & Initialize (10 min)

```bash
# Install beacon with all optional dependencies
pip install -e ".[dev,scraping,llm,docs]"

# Initialize the database with 38+ AI-first companies
beacon init
```

Verify: `beacon stats` should show companies, signals, and tools.

## 2. Build Your Profile (30–60 min)

**Option A: Interactive interview** (recommended for first-time setup)
```bash
beacon profile interview
# Or section by section:
beacon profile interview --section work
beacon profile interview --section projects
beacon profile interview --section skills
```

**Option B: JSON import** (if you already have structured data)
```bash
beacon profile import data/michael-pawlus-profile.json
```

Check completeness:
```bash
beacon profile stats
```

## 3. Configure Search Preferences

```bash
# Create default configuration
beacon config init

# Set notification email
beacon config set notification_email you@example.com

# Set SMTP for email notifications (Gmail example)
beacon config set smtp_host smtp.gmail.com
beacon config set smtp_port 587
beacon config set smtp_user you@gmail.com
beacon config set smtp_password your-app-password

# Set minimum relevance for alerts
beacon config set min_relevance_alert 7.0

# Review all settings
beacon config show
```

## 4. First Scan + Dashboard Review

```bash
# Scan all company career pages
beacon scan

# View the dashboard
beacon dashboard

# See detailed job listings
beacon jobs --min-relevance 7.0

# View a specific job
beacon job show <id>
```

## 5. Apply to Your First Job (Full Workflow)

```bash
# Generate tailored resume + cover letter
beacon job apply <job_id> --generate

# Or generate materials separately:
beacon profile resume <job_id> --format markdown
beacon profile cover-letter <job_id>

# Track your application
beacon application list
```

## 6. Set Up Automation + Notifications

```bash
# Test notifications
beacon automation test-notify

# Install cron job (scans every 6 hours)
beacon automation cron install --every 6

# Check cron status
beacon automation cron status

# Manual automation run
beacon automation run
```

## 7. Build Professional Presence

```bash
# Generate GitHub README
beacon presence github --output README.md

# Generate LinkedIn content
beacon presence linkedin-headline
beacon presence linkedin-about
beacon presence linkedin-post --topic "AI in data science"

# Generate blog content
beacon presence blog-generate --topic "your topic"

# Set up content calendar
beacon presence calendar-seed

# Export personal website
beacon presence site-generate
```

## 8. Profile Completeness Checklist

- [ ] At least 1 work experience with achievements and technologies
- [ ] At least 2 projects with descriptions and outcomes
- [ ] At least 5 skills across categories (language, framework, tool, domain)
- [ ] At least 1 education entry
- [ ] Publications/talks (optional but recommended)
- [ ] Enrichment interviews for key accomplishments

Check status: `beacon profile stats`

## Quick Reference

| Task | Command |
|------|---------|
| Dashboard | `beacon dashboard` |
| Scan jobs | `beacon scan` |
| Top matches | `beacon jobs --min-relevance 7.0` |
| Apply | `beacon job apply <id> --generate` |
| Record outcome | `beacon application outcome <id> --outcome phone_screen` |
| Content ideas | `beacon presence calendar-seed` |
| Full help | `beacon --help` |
