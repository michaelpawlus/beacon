"""Database initialization and connection management for Beacon."""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "beacon.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | str | None = None) -> None:
    """Initialize the database with the schema."""
    conn = get_connection(db_path)
    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)
    _run_migrations(conn)
    conn.commit()
    conn.close()


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Run safe ALTER TABLE migrations for columns added after initial release."""
    _add_column_if_missing(conn, "job_listings", "highlights", "TEXT")
    _add_column_if_missing(conn, "job_listings", "archetype", "TEXT")
    _add_column_if_missing(conn, "job_listings", "archetype_confidence", "REAL")
    _add_column_if_missing(conn, "discovery_candidates", "discovery_score", "REAL DEFAULT 0")
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS role_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL,
            source_job_id INTEGER REFERENCES job_listings(id) ON DELETE SET NULL,
            source_url TEXT,
            archetype TEXT,
            horizon TEXT CHECK(horizon IN ('1y','2y','3y','4y')),
            target_comp_min INTEGER,
            target_comp_max INTEGER,
            description_snapshot TEXT,
            required_skills TEXT,
            why TEXT,
            status TEXT DEFAULT 'active' CHECK(status IN ('active','achieved','dropped')),
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS role_fit_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_target_id INTEGER NOT NULL REFERENCES role_targets(id) ON DELETE CASCADE,
            fit_score REAL,
            gaps_json TEXT,
            evidence_json TEXT,
            computed_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS role_dispatches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT,
            source TEXT,
            author TEXT,
            author_role TEXT,
            role_target_id INTEGER REFERENCES role_targets(id) ON DELETE SET NULL,
            attributes TEXT,
            takeaways TEXT,
            quote TEXT,
            date_published TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS role_market_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            archetype TEXT NOT NULL,
            captured_at TEXT DEFAULT (datetime('now')),
            listings_sampled INTEGER,
            avg_comp_min REAL,
            avg_comp_max REAL,
            top_skills TEXT,
            seniority_mix TEXT,
            comp_signals TEXT,
            basket_json TEXT,
            trends TEXT,
            direction TEXT,
            diff_vs_previous TEXT,
            notes TEXT
        );"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS job_requirements (
            job_id INTEGER PRIMARY KEY REFERENCES job_listings(id) ON DELETE CASCADE,
            required_skills TEXT,
            preferred_skills TEXT,
            keywords TEXT,
            seniority TEXT,
            extracted_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    """Add a column to a table if it doesn't already exist."""
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def reset_db(db_path: Path | str | None = None) -> None:
    """Drop all tables and reinitialize. Use with caution."""
    conn = get_connection(db_path)
    tables = [
        "role_market_snapshots",
        "role_dispatches", "role_fit_snapshots", "role_targets",
        "interview_stories", "wins",
        "skill_gaps",
        "discovery_candidates",
        "network_contact_events", "network_contacts", "network_events",
        "media_log", "sessions", "presentations", "speaker_profile",
        "automation_log", "signal_refresh_log", "resume_variants",
        "application_outcomes",
        "accomplishments", "content_calendar", "content_drafts",
        "applications", "publications_talks", "education", "skills",
        "projects", "work_experiences",
        "score_breakdown", "tools_adopted", "leadership_signals",
        "ai_signals", "job_requirements", "job_listings", "companies"
    ]
    for table in tables:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    conn.close()
    init_db(db_path)
