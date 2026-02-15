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
    conn.commit()
    conn.close()


def reset_db(db_path: Path | str | None = None) -> None:
    """Drop all tables and reinitialize. Use with caution."""
    conn = get_connection(db_path)
    tables = [
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
