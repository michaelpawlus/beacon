# Beacon Best Practices

Recommended cadences and workflows for getting the most out of Beacon.

## Daily (5 minutes)

```bash
beacon dashboard           # Review action items
beacon jobs --new          # Check new matches from overnight scan
```

- Review any new high-relevance jobs (score >= 7.0)
- Apply to strong matches immediately while they're fresh
- Record outcomes for applications you've heard back about

## Weekly (30 minutes)

```bash
beacon application outcomes               # Review recent outcomes
beacon presence calendar                  # Check content calendar
beacon presence linkedin-post --topic "..." # Draft one piece of content
```

- Record outcomes for all pending applications
- Check your content calendar for upcoming items
- Draft at least one piece of content (LinkedIn post, blog outline)
- Review and publish any finished drafts

## Bi-Weekly (1 hour)

```bash
beacon scan                              # Full scan of all companies
beacon report scoring-feedback           # Review scoring calibration
beacon report variant-effectiveness      # Check resume variant performance
beacon scores                            # Refresh company scores
```

- Run a manual full scan to catch anything cron missed
- Review the scoring feedback report — are high-scored jobs converting?
- Check variant effectiveness — which resume approach works best?
- Refresh stale company signals

## Monthly

```bash
beacon automation agents                 # Run all agents
beacon report variant-effectiveness      # Deep review of variants
beacon profile stats                     # Check profile completeness
```

- Run the full agent suite for comprehensive analysis
- Deep review of variant effectiveness across all applications
- Update your profile with new skills, projects, or accomplishments
- Run enrichment interviews for recent work accomplishments
- Review and update your personal website

## Tips

1. **Record outcomes promptly** — the feedback loop only works with data
2. **Use variant labels consistently** — "technical_focus", "leadership_focus", "data_heavy"
3. **Keep signals fresh** — stale company data leads to inaccurate scoring
4. **Publish content regularly** — consistency matters more than perfection
5. **Review the dashboard daily** — it surfaces what needs attention
6. **Trust the scoring but verify** — calibration improves with more outcome data
