-- Beacon: AI-First Company Intelligence Database
-- Schema v0.1.0

-- Core company information
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    domain TEXT,
    careers_url TEXT,
    careers_platform TEXT,  -- greenhouse, lever, ashby, workday, custom
    hq_location TEXT,
    remote_policy TEXT CHECK(remote_policy IN ('remote-first', 'hybrid', 'onsite', 'flexible', 'unknown')),
    size_bucket TEXT CHECK(size_bucket IN ('startup-<50', 'small-50-200', 'mid-200-1000', 'large-1000-5000', 'enterprise-5000+')),
    industry TEXT,
    founded_year INTEGER,
    description TEXT,
    ai_first_score REAL DEFAULT 0,
    ai_posture TEXT,            -- ai_native | ai_forward | ai_curious (see beacon/research/posture.py)
    posture_confidence REAL,   -- 0-1 classifier confidence
    tier INTEGER DEFAULT 4 CHECK(tier BETWEEN 1 AND 4),
    last_researched_at TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Evidence of AI-first culture (general signals)
CREATE TABLE IF NOT EXISTS ai_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    signal_type TEXT NOT NULL CHECK(signal_type IN (
        'leadership_statement',
        'engineering_blog',
        'job_posting_language',
        'conference_talk',
        'employee_report',
        'press_coverage',
        'github_activity',
        'company_policy',
        'product_integration',
        'tool_mandate'
    )),
    title TEXT NOT NULL,
    source_url TEXT,
    source_name TEXT,
    excerpt TEXT,
    signal_strength INTEGER CHECK(signal_strength BETWEEN 1 AND 5),
    date_observed TEXT,
    verified BOOLEAN DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Leadership buy-in evidence
CREATE TABLE IF NOT EXISTS leadership_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    leader_name TEXT NOT NULL,
    leader_title TEXT,
    signal_type TEXT CHECK(signal_type IN ('quote', 'policy', 'memo', 'talk', 'tweet', 'interview')),
    content TEXT NOT NULL,
    source_url TEXT,
    date_observed TEXT,
    impact_level TEXT CHECK(impact_level IN ('company-wide', 'engineering', 'team', 'personal')),
    created_at TEXT DEFAULT (datetime('now'))
);

-- AI tools explicitly adopted/encouraged
CREATE TABLE IF NOT EXISTS tools_adopted (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    adoption_level TEXT CHECK(adoption_level IN ('required', 'encouraged', 'allowed', 'exploring', 'rumored')),
    evidence_url TEXT,
    evidence_excerpt TEXT,
    date_observed TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Scoring breakdown (cached computation)
CREATE TABLE IF NOT EXISTS score_breakdown (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE UNIQUE,
    leadership_score REAL DEFAULT 0,
    tool_adoption_score REAL DEFAULT 0,
    culture_score REAL DEFAULT 0,
    evidence_depth_score REAL DEFAULT 0,
    recency_score REAL DEFAULT 0,
    composite_score REAL DEFAULT 0,
    last_computed_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Job listings (Phase 2: Job Scanner & Monitoring)
CREATE TABLE IF NOT EXISTS job_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    url TEXT,
    location TEXT,
    department TEXT,
    description_text TEXT,
    date_posted TEXT,
    date_first_seen TEXT DEFAULT (datetime('now')),
    date_last_seen TEXT DEFAULT (datetime('now')),
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'closed', 'applied', 'ignored')),
    relevance_score REAL DEFAULT 0,
    match_reasons TEXT,  -- JSON array of reasons
    highlights TEXT,  -- JSON: salary, AI tools, experience extracted from description
    archetype TEXT,  -- role archetype key (see beacon/research/archetypes.py)
    archetype_confidence REAL,  -- 0-1 classifier confidence
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(company_id, title, url)
);

-- Skill gap tracking
CREATE TABLE IF NOT EXISTS skill_gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,
    category TEXT,
    demand_count INTEGER DEFAULT 0,
    example_jobs TEXT,  -- JSON array of {id, title, company}
    status TEXT DEFAULT 'open' CHECK(status IN ('open', 'learning', 'closed')),
    priority INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(skill_name)
);

-- Phase 3: Professional Profile & Application Materials

-- Work experience history
CREATE TABLE IF NOT EXISTS work_experiences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    start_date TEXT NOT NULL,  -- YYYY-MM or YYYY-MM-DD
    end_date TEXT,             -- NULL = current role
    description TEXT,
    key_achievements TEXT,     -- JSON array
    technologies TEXT,         -- JSON array
    metrics TEXT,              -- JSON array of quantified results
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Projects (optionally linked to work experience)
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    technologies TEXT,         -- JSON array
    outcomes TEXT,             -- JSON array
    repo_url TEXT,
    is_public BOOLEAN DEFAULT 0,
    work_experience_id INTEGER REFERENCES work_experiences(id) ON DELETE SET NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Skills inventory
CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT,             -- e.g., 'language', 'framework', 'tool', 'domain'
    proficiency TEXT CHECK(proficiency IN ('beginner', 'intermediate', 'advanced', 'expert')),
    years_experience INTEGER,
    evidence TEXT,             -- JSON array of evidence references
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Education
CREATE TABLE IF NOT EXISTS education (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    institution TEXT NOT NULL,
    degree TEXT,
    field_of_study TEXT,
    start_date TEXT,
    end_date TEXT,
    gpa REAL,
    relevant_coursework TEXT,  -- JSON array
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Publications, talks, and other public contributions
CREATE TABLE IF NOT EXISTS publications_talks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    pub_type TEXT NOT NULL CHECK(pub_type IN (
        'blog_post', 'paper', 'talk', 'panel', 'podcast', 'workshop', 'open_source', 'book'
    )),
    venue TEXT,
    url TEXT,
    date_published TEXT,
    description TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Application tracking (links to job_listings)
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES job_listings(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'draft' CHECK(status IN (
        'draft', 'applied', 'phone_screen', 'interview', 'offer', 'rejected', 'withdrawn', 'ghosted'
    )),
    resume_path TEXT,
    cover_letter_path TEXT,
    applied_date TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Phase 4: Professional Presence Automation

-- Content drafts for GitHub, LinkedIn, blog posts, etc.
CREATE TABLE IF NOT EXISTS content_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type TEXT NOT NULL,
    platform TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft', 'published', 'archived')),
    published_url TEXT,
    published_at TEXT,
    metadata TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Content calendar for planning posts
CREATE TABLE IF NOT EXISTS content_calendar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    platform TEXT NOT NULL,
    content_type TEXT NOT NULL,
    topic TEXT,
    target_date TEXT,
    status TEXT DEFAULT 'idea' CHECK(status IN ('idea', 'outlined', 'drafted', 'published')),
    draft_id INTEGER REFERENCES content_drafts(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Enrichment accomplishments for deep-dive interviews
CREATE TABLE IF NOT EXISTS accomplishments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_experience_id INTEGER REFERENCES work_experiences(id) ON DELETE SET NULL,
    raw_statement TEXT NOT NULL,
    context TEXT,
    action TEXT,
    result TEXT,
    metrics TEXT,
    technologies TEXT,
    stakeholders TEXT,
    timeline TEXT,
    challenges TEXT,
    learning TEXT,
    content_angles TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Phase 5: Feedback tracking

-- Application outcomes for feedback loop
CREATE TABLE IF NOT EXISTS application_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    outcome TEXT NOT NULL CHECK(outcome IN (
        'no_response', 'rejection_auto', 'rejection_human',
        'phone_screen', 'technical', 'onsite', 'offer', 'accepted'
    )),
    response_days INTEGER,
    notes TEXT,
    recorded_at TEXT DEFAULT (datetime('now'))
);

-- Resume variant tracking
CREATE TABLE IF NOT EXISTS resume_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    variant_label TEXT NOT NULL,
    strategy_notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Signal refresh tracking
CREATE TABLE IF NOT EXISTS signal_refresh_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    signals_added INTEGER DEFAULT 0,
    signals_updated INTEGER DEFAULT 0,
    refreshed_at TEXT DEFAULT (datetime('now'))
);

-- Automation run log
CREATE TABLE IF NOT EXISTS automation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL CHECK(run_type IN ('full', 'scan', 'digest', 'signal_refresh')),
    started_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    jobs_found INTEGER DEFAULT 0,
    new_relevant_jobs INTEGER DEFAULT 0,
    notifications_sent INTEGER DEFAULT 0,
    signals_refreshed INTEGER DEFAULT 0,
    errors TEXT,
    duration_seconds REAL
);

-- Presentations (talks, workshops, panels)
CREATE TABLE IF NOT EXISTS presentations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    abstract TEXT,
    key_points TEXT,         -- JSON array of key points
    event_name TEXT,
    venue TEXT,
    event_url TEXT,
    date TEXT,               -- YYYY-MM-DD
    duration_minutes INTEGER,
    audience TEXT,
    status TEXT DEFAULT 'planned' CHECK(status IN ('planned', 'accepted', 'delivered', 'cancelled')),
    slides_url TEXT,
    recording_url TEXT,
    co_presenters TEXT,      -- JSON array of co-presenter names
    tags TEXT,               -- JSON array of tags
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Speaker profile (single-row table)
CREATE TABLE IF NOT EXISTS speaker_profile (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    headshot_path TEXT,
    short_bio TEXT,
    long_bio TEXT,
    bio_generated_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Media log — videos, podcasts, articles consumed with personal reactions
CREATE TABLE IF NOT EXISTS media_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT,
    source_type TEXT NOT NULL CHECK(source_type IN ('video', 'podcast', 'article', 'talk', 'course', 'book')),
    creator TEXT,                -- channel name, author, speaker
    platform TEXT,               -- YouTube, Spotify, etc.
    date_consumed TEXT,          -- YYYY-MM-DD
    rating INTEGER CHECK(rating BETWEEN 1 AND 5),
    tags TEXT,                   -- JSON array
    key_takeaways TEXT,          -- free-text notes on what you learned
    personal_reaction TEXT,      -- your feelings, philosophy alignment, opinions
    team_shareable BOOLEAN DEFAULT 0,
    share_note TEXT,             -- simplified blurb for team sharing
    why_it_matters TEXT,         -- why this matters to the team / org
    key_quotes TEXT,             -- JSON array of notable quotes or lines
    share_category TEXT,         -- structured category for sharing (e.g. AI Adoption, Leadership)
    content_draft_id INTEGER REFERENCES content_drafts(id) ON DELETE SET NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Claude Code session logs (for portfolio / application materials)
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    project TEXT NOT NULL DEFAULT 'beacon',
    summary TEXT NOT NULL,
    challenges TEXT,        -- JSON array
    technologies TEXT,      -- JSON array
    impact TEXT,
    tags TEXT,              -- JSON array
    transcript_path TEXT,
    obsidian_path TEXT,
    duration_estimate TEXT,
    session_date TEXT DEFAULT (date('now')),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Networking: events attended
CREATE TABLE IF NOT EXISTS network_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    organizer TEXT,
    event_type TEXT DEFAULT 'meetup' CHECK(event_type IN ('meetup', 'conference', 'workshop', 'hackathon', 'networking', 'other')),
    url TEXT,
    location TEXT,
    date TEXT,                   -- YYYY-MM-DD
    description TEXT,
    attendee_count INTEGER,
    status TEXT DEFAULT 'upcoming' CHECK(status IN ('upcoming', 'attended', 'cancelled', 'skipped')),
    tags TEXT,                   -- JSON array
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Networking: contacts / people in your professional network
CREATE TABLE IF NOT EXISTS network_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    title TEXT,
    company TEXT,
    company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL,
    email TEXT,
    linkedin_url TEXT,
    bio TEXT,
    interests TEXT,              -- JSON array
    priority INTEGER DEFAULT 0 CHECK(priority BETWEEN 0 AND 5),
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Networking: many-to-many link between contacts and events
CREATE TABLE IF NOT EXISTS network_contact_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL REFERENCES network_contacts(id) ON DELETE CASCADE,
    event_id INTEGER NOT NULL REFERENCES network_events(id) ON DELETE CASCADE,
    topics_discussed TEXT,
    follow_up TEXT,
    followed_up BOOLEAN DEFAULT 0,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(contact_id, event_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project);
CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(session_date DESC);
CREATE INDEX IF NOT EXISTS idx_companies_score ON companies(ai_first_score DESC);
CREATE INDEX IF NOT EXISTS idx_companies_tier ON companies(tier);
CREATE INDEX IF NOT EXISTS idx_signals_company ON ai_signals(company_id);
CREATE INDEX IF NOT EXISTS idx_signals_type ON ai_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_leadership_company ON leadership_signals(company_id);
CREATE INDEX IF NOT EXISTS idx_tools_company ON tools_adopted(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON job_listings(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON job_listings(status);
CREATE INDEX IF NOT EXISTS idx_projects_work_exp ON projects(work_experience_id);
CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);
CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_content_drafts_platform ON content_drafts(platform);
CREATE INDEX IF NOT EXISTS idx_content_drafts_status ON content_drafts(status);
CREATE INDEX IF NOT EXISTS idx_content_calendar_platform ON content_calendar(platform);
CREATE INDEX IF NOT EXISTS idx_content_calendar_status ON content_calendar(status);
CREATE INDEX IF NOT EXISTS idx_accomplishments_work_exp ON accomplishments(work_experience_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_application ON application_outcomes(application_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_outcome ON application_outcomes(outcome);
CREATE INDEX IF NOT EXISTS idx_resume_variants_application ON resume_variants(application_id);
CREATE INDEX IF NOT EXISTS idx_signal_refresh_company ON signal_refresh_log(company_id);
CREATE INDEX IF NOT EXISTS idx_automation_log_type ON automation_log(run_type);
CREATE INDEX IF NOT EXISTS idx_automation_log_started ON automation_log(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_presentations_status ON presentations(status);
CREATE INDEX IF NOT EXISTS idx_presentations_date ON presentations(date);
CREATE INDEX IF NOT EXISTS idx_media_log_source_type ON media_log(source_type);
CREATE INDEX IF NOT EXISTS idx_media_log_team_shareable ON media_log(team_shareable);
CREATE INDEX IF NOT EXISTS idx_media_log_date ON media_log(date_consumed DESC);
CREATE INDEX IF NOT EXISTS idx_media_log_rating ON media_log(rating DESC);
CREATE INDEX IF NOT EXISTS idx_network_events_date ON network_events(date DESC);
CREATE INDEX IF NOT EXISTS idx_network_events_status ON network_events(status);
CREATE INDEX IF NOT EXISTS idx_network_contacts_company ON network_contacts(company);
CREATE INDEX IF NOT EXISTS idx_network_contacts_company_id ON network_contacts(company_id);
CREATE INDEX IF NOT EXISTS idx_network_contacts_priority ON network_contacts(priority DESC);
CREATE INDEX IF NOT EXISTS idx_network_ce_contact ON network_contact_events(contact_id);
CREATE INDEX IF NOT EXISTS idx_network_ce_event ON network_contact_events(event_id);

-- Discovery candidates — companies surfaced by source adapters, awaiting review
CREATE TABLE IF NOT EXISTS discovery_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT,
    careers_url TEXT,
    hq_location TEXT,
    industry TEXT,
    signals_json TEXT,                          -- JSON-serialized list[dict]
    raw_json TEXT,                              -- full source record (audit trail)
    discovery_score REAL DEFAULT 0,             -- evidence-weighted ranking score
    ai_posture TEXT,                            -- ai_native | ai_forward | ai_curious (derived from signals)
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'promoted', 'rejected')),
    reject_reason TEXT,
    promoted_to_company_id INTEGER REFERENCES companies(id),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source, source_ref)
);

CREATE INDEX IF NOT EXISTS idx_candidates_status ON discovery_candidates(status);
CREATE INDEX IF NOT EXISTS idx_candidates_source ON discovery_candidates(source);
CREATE INDEX IF NOT EXISTS idx_candidates_score ON discovery_candidates(discovery_score DESC);

-- Career OS: win / evidence log — brag-document discipline from day one.
-- Wins are logged as they happen at the current job and later distilled into
-- interview stories (interview_stories.id lands with #30; plain column until then).
CREATE TABLE IF NOT EXISTS wins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    win_date TEXT DEFAULT (date('now')),
    category TEXT CHECK(category IN ('delivery','adoption','enablement','relationship','revenue','learning','visibility','process')),
    description TEXT,
    impact TEXT,
    metrics TEXT,             -- JSON array of quantified results
    stakeholders TEXT,        -- JSON array
    technologies TEXT,        -- JSON array
    tags TEXT,                -- JSON array
    work_experience_id INTEGER REFERENCES work_experiences(id) ON DELETE SET NULL,
    session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    story_id INTEGER,         -- set when promoted to an interview story (#30)
    visibility TEXT DEFAULT 'private' CHECK(visibility IN ('private','team','public')),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_wins_category ON wins(category);
CREATE INDEX IF NOT EXISTS idx_wins_date ON wins(win_date DESC);

-- Career OS: STAR+Reflection interview story bank (#30). Stories are distilled
-- from wins (`beacon career win promote`) or captured directly; the Reflection
-- field is the seniority signal and gates promotion from draft to polished.
CREATE TABLE IF NOT EXISTS interview_stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    situation TEXT,
    task TEXT,
    action TEXT,
    result TEXT,
    reflection TEXT,          -- lesson extracted; required for status='polished'
    archetypes TEXT,          -- JSON array of archetype keys (beacon/research/archetypes.py)
    tags TEXT,                -- JSON array (leadership, ambiguity, failure, scope-cut, ...)
    target_role_ids TEXT,     -- JSON array of role_targets ids (#43; plain column until then)
    linked_work_id INTEGER REFERENCES work_experiences(id) ON DELETE SET NULL,
    win_id INTEGER REFERENCES wins(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','polished','retired')),
    times_used INTEGER DEFAULT 0,
    last_used_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_stories_status ON interview_stories(status);

-- Career OS: aspirational role targets (#43, WS3). Named roles the user is
-- *not yet qualified for*, with the JD frozen at capture time so the demand
-- side survives the posting. Fit is measured as a time series (see
-- role_fit_snapshots) so skill investment over 2–4 years is deliberate.
CREATE TABLE IF NOT EXISTS role_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL,   -- optional exemplar employer
    source_job_id INTEGER REFERENCES job_listings(id) ON DELETE SET NULL,
    source_url TEXT,
    archetype TEXT,
    horizon TEXT CHECK(horizon IN ('1y','2y','3y','4y')),
    target_comp_min INTEGER,
    target_comp_max INTEGER,
    description_snapshot TEXT,        -- JD frozen at capture (postings die; targets don't)
    required_skills TEXT,             -- JSON array of canonical skill names
    why TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','achieved','dropped')),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_role_targets_status ON role_targets(status);
CREATE INDEX IF NOT EXISTS idx_role_targets_horizon ON role_targets(horizon);

-- Career OS: fit-over-time snapshots — one row per `beacon target fit` run.
-- "fit 5.2 in June 2026 → 7.4 by mid-2027" is the core deliverable.
CREATE TABLE IF NOT EXISTS role_fit_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_target_id INTEGER NOT NULL REFERENCES role_targets(id) ON DELETE CASCADE,
    fit_score REAL,
    gaps_json TEXT,           -- missing skills at compute time
    evidence_json TEXT,       -- matched skills + wins/stories backing them
    computed_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_fit_snapshots_target ON role_fit_snapshots(role_target_id, computed_at DESC);

-- Career OS: dispatches from real FDEs in the wild — blog posts, talks,
-- podcasts by people doing the target roles. Captures the attributes that
-- actually make them successful, so target gap analysis can show where the
-- JD-demanded skill list and field reality diverge.
CREATE TABLE IF NOT EXISTS role_dispatches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT,
    source TEXT,              -- blog, podcast, talk, linkedin, forum, ...
    author TEXT,
    author_role TEXT,         -- e.g. "FDE @ Palantir"
    role_target_id INTEGER REFERENCES role_targets(id) ON DELETE SET NULL,
    attributes TEXT,          -- JSON array of observed success attributes/skills
    takeaways TEXT,
    quote TEXT,
    date_published TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_dispatches_target ON role_dispatches(role_target_id);

-- Career OS: role-market radar (#44, WS4). One row per `beacon career market`
-- run — a quarterly snapshot of an FDE/applied-AI role *family* (a basket of
-- equivalent titles, not a single posting). Tracks the category's salary,
-- skill mix, seniority mix, and headcount over time, plus a "basket" of
-- recurring exemplar roles (Palantir + frontier-lab FDEs) whose comp is
-- re-checked each quarter. `diff_vs_previous` is the headline: which skills are
-- rising/falling and where comp bands moved since last quarter (absorbs #21).
CREATE TABLE IF NOT EXISTS role_market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archetype TEXT NOT NULL,              -- role-family key (e.g. 'solutions_fde')
    captured_at TEXT DEFAULT (datetime('now')),
    since_days INTEGER,                   -- listing window (NULL = all active); diffs only compare same-window runs
    listings_sampled INTEGER,             -- # equivalent-title listings in scope (headcount proxy)
    avg_comp_min REAL,                    -- mean of listing salary floors with comp
    avg_comp_max REAL,                    -- mean of listing salary ceilings with comp
    top_skills TEXT,                      -- JSON [{skill, count}]
    seniority_mix TEXT,                   -- JSON {bucket: count}
    comp_signals TEXT,                    -- JSON [{source, range, url}] from web (absorbs #21)
    basket_json TEXT,                     -- JSON: tracked recurring roles + comp + average
    trends TEXT,                          -- JSON from LLM web search
    direction TEXT,                       -- growing|shrinking|stable|unknown (category pulse)
    diff_vs_previous TEXT,                -- JSON: skills rising/falling/added/removed + deltas
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_family ON role_market_snapshots(archetype, captured_at DESC);

-- Cached structured requirements for a job listing — populated on first
-- `beacon match-jobs` run per listing, refreshed when the listing's
-- date_last_seen advances past extracted_at.
CREATE TABLE IF NOT EXISTS job_requirements (
    job_id INTEGER PRIMARY KEY REFERENCES job_listings(id) ON DELETE CASCADE,
    required_skills TEXT,    -- JSON array
    preferred_skills TEXT,   -- JSON array
    keywords TEXT,           -- JSON array
    seniority TEXT,
    extracted_at TEXT NOT NULL DEFAULT (datetime('now'))
);
