# Beacon User Roadmap

A guide for building momentum with Beacon over time.

## Immediate: Setup (Day 1)

1. Install and initialize: `beacon init`
2. Import or build your profile: `beacon profile interview`
3. Configure notifications: `beacon config init` → set email/SMTP
4. Run your first scan: `beacon scan`
5. Review the dashboard: `beacon dashboard`
6. Set up automation: `beacon automation cron install --every 6`

## Week 1–2: First Applications

1. Apply to your top 5 matches: `beacon job apply <id> --generate`
2. Record outcomes as you hear back: `beacon application outcome <id> --outcome <type>`
3. Generate your first blog post or LinkedIn content
4. Complete enrichment interviews for top accomplishments
5. Track resume variants: note which approach you used for each application

## Month 1: Build the Feedback Loop

1. Accumulate at least 10 application outcomes
2. Run `beacon report scoring-feedback` to check calibration
3. Publish your personal website: `beacon presence site-generate`
4. Optimize your LinkedIn profile with generated content
5. Build a weekly rhythm with the content calendar
6. Review variant effectiveness: `beacon report variant-effectiveness`

## Month 2+: Optimize and Scale

1. Run agents regularly: `beacon automation agents`
2. Review and adjust scoring based on calibration feedback
3. Refine resume variants based on what's working
4. Keep content calendar active and publish consistently
5. Refresh stale company signals as the market evolves
6. Update profile with new projects and accomplishments

## Future Enhancements (Post-Phase 5)

Ideas for future development:

- **Web dashboard** — browser-based UI for visual exploration
- **Slack integration** — notifications and quick actions via Slack
- **Browser extension** — auto-detect job listings while browsing
- **LinkedIn API** — auto-post content to LinkedIn
- **Advanced analytics** — salary data, market trends, industry mapping
- **Multi-user support** — share company intelligence across a team
- **Resume A/B testing** — systematic variant testing with statistical significance
