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

-- Job listings (Phase 2, but define schema now)
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
    created_at TEXT DEFAULT (datetime('now'))
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
