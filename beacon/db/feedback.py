"""Feedback tracking database operations for Beacon Phase 5."""

import sqlite3

VALID_OUTCOMES = (
    "no_response", "rejection_auto", "rejection_human",
    "phone_screen", "technical", "onsite", "offer", "accepted",
)


def record_outcome(
    conn: sqlite3.Connection,
    application_id: int,
    outcome: str,
    response_days: int | None = None,
    notes: str | None = None,
) -> int:
    """Record an application outcome. Returns the outcome ID."""
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"Invalid outcome: {outcome}. Must be one of {VALID_OUTCOMES}")

    # Verify application exists
    app = conn.execute("SELECT id FROM applications WHERE id = ?", (application_id,)).fetchone()
    if not app:
        raise ValueError(f"Application {application_id} not found")

    cursor = conn.execute(
        """INSERT INTO application_outcomes (application_id, outcome, response_days, notes)
           VALUES (?, ?, ?, ?)""",
        (application_id, outcome, response_days, notes),
    )
    conn.commit()
    return cursor.lastrowid


def get_outcomes(
    conn: sqlite3.Connection,
    application_id: int | None = None,
    outcome_filter: str | None = None,
) -> list[sqlite3.Row]:
    """Get outcomes with optional filters."""
    query = "SELECT * FROM application_outcomes WHERE 1=1"
    params: list = []
    if application_id is not None:
        query += " AND application_id = ?"
        params.append(application_id)
    if outcome_filter:
        query += " AND outcome = ?"
        params.append(outcome_filter)
    query += " ORDER BY recorded_at DESC"
    return conn.execute(query, params).fetchall()


def get_outcome_stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get aggregated outcome statistics."""
    return conn.execute(
        """SELECT outcome, COUNT(*) as count, AVG(response_days) as avg_days
           FROM application_outcomes
           GROUP BY outcome
           ORDER BY count DESC"""
    ).fetchall()


def record_resume_variant(
    conn: sqlite3.Connection,
    application_id: int,
    variant_label: str,
    strategy_notes: str | None = None,
) -> int:
    """Record a resume variant used for an application. Returns the variant ID."""
    cursor = conn.execute(
        """INSERT INTO resume_variants (application_id, variant_label, strategy_notes)
           VALUES (?, ?, ?)""",
        (application_id, variant_label, strategy_notes),
    )
    conn.commit()
    return cursor.lastrowid


def get_variant_effectiveness(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get resume variant usage counts."""
    return conn.execute(
        """SELECT variant_label, COUNT(*) as count
           FROM resume_variants
           GROUP BY variant_label
           ORDER BY count DESC"""
    ).fetchall()


def get_scoring_feedback(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get outcome data joined with job relevance scores for calibration."""
    return conn.execute(
        """SELECT ao.outcome, ao.response_days, j.relevance_score, c.name as company_name
           FROM application_outcomes ao
           JOIN applications a ON ao.application_id = a.id
           JOIN job_listings j ON a.job_id = j.id
           JOIN companies c ON j.company_id = c.id
           ORDER BY j.relevance_score DESC"""
    ).fetchall()


def record_signal_refresh(
    conn: sqlite3.Connection,
    company_id: int,
    signals_added: int = 0,
    signals_updated: int = 0,
) -> int:
    """Log a signal refresh for a company. Returns the log ID."""
    cursor = conn.execute(
        """INSERT INTO signal_refresh_log (company_id, signals_added, signals_updated)
           VALUES (?, ?, ?)""",
        (company_id, signals_added, signals_updated),
    )
    conn.commit()
    return cursor.lastrowid


def get_signal_refresh_log(
    conn: sqlite3.Connection,
    company_id: int | None = None,
    limit: int = 50,
) -> list[sqlite3.Row]:
    """Get signal refresh history."""
    query = "SELECT * FROM signal_refresh_log WHERE 1=1"
    params: list = []
    if company_id is not None:
        query += " AND company_id = ?"
        params.append(company_id)
    query += " ORDER BY refreshed_at DESC LIMIT ?"
    params.append(limit)
    return conn.execute(query, params).fetchall()
