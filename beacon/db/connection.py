"""Database initialization and connection management for Beacon."""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "beacon.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Get a database connection with row factory enabled.

    Self-heals an already-initialized DB to the latest schema (see
    `_ensure_migrated`) so commands that open a bare connection — rather than
    going through `init_db()` — don't trip over columns added by a later
    release (e.g. `ai_posture`, #46) on an upgraded-but-not-reinitialized DB.
    """
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_migrated(conn)
    return conn


def _ensure_migrated(conn: sqlite3.Connection) -> None:
    """Idempotently bring an *already-initialized* DB up to the latest schema.

    A brand-new DB has no `companies` table yet — `init_db()` owns full setup
    there, so skip until it exists (and to avoid ALTERing tables that aren't
    created yet). On a steady-state DB every migration is a no-op, so this adds
    only a cheap sqlite_master lookup per connection; the one upgrade run that
    adds columns + backfills posture is committed so later reads see it.
    """
    initialized = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='companies'"
    ).fetchone()
    if not initialized:
        return
    _run_migrations(conn)
    conn.commit()


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
    # AI posture (#46): native / forward / curious, derived from the signal mix.
    _add_column_if_missing(conn, "companies", "ai_posture", "TEXT")
    _add_column_if_missing(conn, "companies", "posture_confidence", "REAL")
    _add_column_if_missing(conn, "discovery_candidates", "ai_posture", "TEXT")
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
            since_days INTEGER,
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
    # since_days was added after role_market_snapshots first shipped — a DB
    # created by an earlier build keeps its table untouched by CREATE IF NOT
    # EXISTS, so window-aware diffing would hit "no such column" without this.
    _add_column_if_missing(conn, "role_market_snapshots", "since_days", "INTEGER")
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

    _backfill_posture(conn)


def _backfill_posture(conn: sqlite3.Connection) -> None:
    """Stamp `ai_posture` on rows that predate the column (#46).

    On an upgraded DB the ALTER above adds `ai_posture` as NULL for existing
    rows. Companies wait for the next `beacon scores`, and pending
    `discovery_candidates` re-surfaced by a source hit the dedupe `continue`
    before classification — so without this, `--posture` filters silently hide
    those rows. Idempotent: only touches rows still NULL.
    """
    import json

    from beacon.research.posture import classify_candidate, classify_company
    from beacon.sources.base import Candidate
    from beacon.sources.dedupe import score_candidate

    company_ids = [
        r["id"] for r in conn.execute(
            "SELECT id FROM companies WHERE ai_posture IS NULL"
        ).fetchall()
    ]
    for cid in company_ids:
        res = classify_company(conn, cid)
        conn.execute(
            "UPDATE companies SET ai_posture = ?, posture_confidence = ? WHERE id = ?",
            (res.posture, res.confidence, cid),
        )

    cand_rows = conn.execute(
        "SELECT * FROM discovery_candidates WHERE ai_posture IS NULL"
    ).fetchall()
    for row in cand_rows:
        try:
            signals = json.loads(row["signals_json"]) if row["signals_json"] else []
        except (json.JSONDecodeError, TypeError):
            signals = []
        res = classify_candidate(signals)
        # Recompute discovery_score too: score_candidate() now folds in a
        # clear-posture bonus, and dedupe skips these rows on re-discovery, so
        # without this they'd stay permanently under-ranked in `candidates`.
        cand = Candidate(
            name=row["name"],
            source=row["source"],
            source_ref=row["source_ref"],
            domain=row["domain"],
            careers_url=row["careers_url"],
            hq_location=row["hq_location"],
            industry=row["industry"],
            signals=signals,
        )
        conn.execute(
            "UPDATE discovery_candidates SET ai_posture = ?, discovery_score = ? WHERE id = ?",
            (res.posture, score_candidate(cand, res), row["id"]),
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
