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
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(company_id, title, url)
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
        'blog_post', 'paper', 'talk', 'panel', 'podcast', 'workshop', 'open_source'
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

-- Indexes
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
