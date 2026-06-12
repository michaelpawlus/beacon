# Beacon v2 — Career Operating System Strategy

*Adopted 2026-06-10, on accepting a Forward Deployed Engineer offer ($113k → $155k
after six flat years). Beacon's job-search mission is complete; this document is
the north star for what it becomes next.*

## North star

**Beacon v1 answered: "Where should I apply next?" Beacon v2 answers: "Am I
compounding?"**

The thesis: models keep getting more powerful, but until diffusion, adoption,
enablement, deployment, and business alignment catch up, there is a persistent
overhang between the *potential* and *realized* value of AI. FDE-type roles
exist to close that overhang, and the people who close it well are paid a
premium. Beacon v2 is the instrument that:

1. **Makes the current FDE job succeed** — an evolving success guide grounded
   in what's actually being done (win mix, gaps, market direction).
2. **Collects evidence from day one** — wins logged as they happen, distilled
   into STAR+Reflection stories, so the next move starts from a full evidence
   base instead of retroactive reconstruction.
3. **Points a 2–4 year vector at named aspirational roles** — roles not yet
   qualified for, with frozen JD snapshots and fit measured over time, so skill
   investments are deliberate.
4. **Watches the shape of the FDE/applied-AI role in the economy** — quarterly
   market snapshots so day-job work choices stay aligned with where the role
   family is heading.

## Compensation trajectory

- 2026: $155k (current move, +37%).
- Market context (June 2026): enterprise FDE roles ~$130–190k; Palantir-tier
  FDE median ~$215k TC; frontier-lab FDEs $350k+ TC, mostly equity.
- **Target: $200–240k at the next move (2028–2030); $250k+ stretch by 2031.**
  $200k-by-2031 alone is ~5% CAGR — achievable with no moves at all — so the
  real goal is the *tier jump*, not the number. One documented FDE tour
  (2–4 years of evidence closing the value overhang at a real enterprise) is
  the qualification for the next tier.
- The role-market radar tracks comp bands quarterly against this line.

## Center of gravity shift

Architecture is unchanged (Typer sub-apps, SQLite, `--json`, `oj capture`).
What changes is which tables are alive:

| | v1 (job search) | v2 (career OS) |
|---|---|---|
| Daily driver | `job_listings`, `applications` | `wins`, `sessions`, `interview_stories` |
| Demand side | active listings, `match-jobs` | `role_targets` + fit snapshots |
| Scanning | daily alerts | quarterly market sampling |
| Presence | "should I post during a search?" | posting as career compounding |

## Workstreams (priority order)

1. **WS1 — Win/evidence log** (`beacon career win add/list/show`, `beacon
   career review`) — **shipped with this doc.** Brag-document discipline;
   categories encode the overhang thesis (`adoption`/`enablement` = diffusion
   work vs `delivery` = build work). Issue #26 (planned metrics) folds in here.
2. **WS2 — STAR+Reflection story bank** (#30, reframed) — stories distilled
   *from wins* via `win promote --to-story`; Reflection is the promotion gate;
   stories map to aspirational targets. Next implementation session.
3. **WS3 — Aspirational role track** (`beacon target ...`) — **shipped
   2026-06 (#43).** `role_targets` with frozen JD snapshots +
   `role_fit_snapshots` time series; gaps analysis scoped to targets
   (horizon-weighted, win-evidence-linked); `role_dispatches` capture field
   reports from real FDEs so JD demands can be checked against reality;
   `beacon target seed` lands the first Palantir-tier + frontier-lab targets.
   Surfaced continuously via dashboard action items and the career review.
4. **WS4 — Role-market radar** (`beacon career market`) — quarterly snapshot
   of the FDE/applied-AI role family (skills, seniority mix, comp signals,
   trends), cloning the `presence radar` two-input pattern. Absorbs #21.
5. **WS5 — FDE success guide** (`beacon career guide`) — deterministic,
   regenerable vault note: thesis → win mix → target gaps → market direction →
   recommended focus → sharing queue (from `media_log`).
6. **WS6 — Skill-investment evaluator** (#35, reframed) — "should I take this
   course / build this project" scored against role targets + current-job
   leverage.
7. **WS7 — Career cadence + integrity** — `orchestrate weekly` (#20) as the
   career heartbeat; `beacon doctor` (#32) with v2-table checks.
8. **WS8 — AI-forward posture in discovery** (low priority) — classify
   `ai_native` / `ai_forward` / `ai_curious` from existing signal mix; closes
   the gap that made the actual employer invisible to v1 discovery.

## Verdict on pre-pivot issues

| Issue | Verdict |
|---|---|
| #38 CI Node bump | Keep — do before June 16 |
| #35 training/project evaluator | Reframe → WS6 (score against role targets) |
| #34 auto-pipeline ingest | Narrow — keep only `target add --url --fetch` front half |
| #33 negotiation playbook | Keep, parked — reframe for next-move + internal promotion case |
| #32 beacon doctor | Keep — add v2-table checks |
| #31 deep job evaluation | Reframe — A–F evaluation of *aspirational* roles |
| #30 story bank | Reframed, next up (WS2) |
| #28 ghost-job legitimacy | Icebox until next active search |
| #26 planned metrics | Fold into WS1 follow-up |
| #24 / #23 / #22 scoring tuning | Reframe into `target fit` ranking; #22 inverts (staff/principal score *high* now); #23 icebox |
| #21 comp research | Absorbed by WS4 radar |
| #20 orchestration hub | Reframe → WS7 weekly career heartbeat |
| #18 interview prep | Deprioritize — superseded by story bank + `materials interview-brief` |
| #17 application analytics | Icebox — no application flow for years |
| #16 daily job alerts | Repurpose cadence: signal refresh + quarterly radar + weekly heartbeat |
| #15 research refresh/add | Close — superseded by `companies discover/refresh-signals` |
| #7–#14 presence/content | Keep, upgraded relevance — visibility compounds toward the 2031 target |

## Operating cadence

- **Continuous:** log wins as they happen (`beacon career win add`), sessions
  as ever (`beacon session log`), media worth sharing (`beacon media add`).
- **Weekly:** career heartbeat (WS7) — wins this week (nudge if zero), untold
  stories, posting gap.
- **Quarterly:** `beacon career review --vault` (brag doc), role-market radar
  run, `beacon target fit --all` snapshot, refresh the success guide.
- **Yearly:** revisit role targets and the comp line; promote/retire stories.
