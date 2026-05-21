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
    _add_column_if_missing(conn, "discovery_candidates", "discovery_score", "REAL DEFAULT 0")
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
        "skill_gaps",
        "discovery_candidates",
        "media_log", "sessions", "presentations", "speaker_profile",
        "automation_log", "signal_refresh_log", "resume_variants",
        "application_outcomes",
        "accomplishments", "content_calendar", "content_drafts",
        "applications", "publications_talks", "education", "skills",
        "projects", "work_experiences",
        "score_breakdown", "tools_adopted", "leadership_signals",
        "ai_signals", "job_listings", "companies"
    ]
    for table in tables:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    conn.close()
    init_db(db_path)
