"""Job listing database operations for Beacon Phase 2."""

import json
import sqlite3


def upsert_job(
    conn: sqlite3.Connection,
    company_id: int,
    title: str,
    url: str | None = None,
    location: str | None = None,
    department: str | None = None,
    description_text: str | None = None,
    date_posted: str | None = None,
    relevance_score: float = 0.0,
    match_reasons: list[str] | None = None,
) -> dict:
    """Insert or update a job listing. Returns {"id": ..., "is_new": bool}."""
    reasons_json = json.dumps(match_reasons) if match_reasons else None

    # Try to find existing job by unique constraint (company_id, title, url)
    existing = conn.execute(
        "SELECT id FROM job_listings WHERE company_id = ? AND title = ? AND url IS ?",
        (company_id, title, url),
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE job_listings
               SET date_last_seen = datetime('now'),
                   location = COALESCE(?, location),
                   department = COALESCE(?, department),
                   description_text = COALESCE(?, description_text),
                   date_posted = COALESCE(?, date_posted),
                   relevance_score = ?,
                   match_reasons = COALESCE(?, match_reasons),
                   status = CASE WHEN status = 'closed' THEN 'active' ELSE status END
               WHERE id = ?""",
            (location, department, description_text, date_posted, relevance_score, reasons_json, existing["id"]),
        )
        conn.commit()
        return {"id": existing["id"], "is_new": False}
    else:
        cursor = conn.execute(
            """INSERT INTO job_listings
               (company_id, title, url, location, department, description_text,
                date_posted, relevance_score, match_reasons)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (company_id, title, url, location, department,
             description_text, date_posted, relevance_score, reasons_json),
        )
        conn.commit()
        return {"id": cursor.lastrowid, "is_new": True}


def mark_stale_jobs(conn: sqlite3.Connection, company_id: int, active_urls: set[str | None]) -> int:
    """Mark jobs as closed if they weren't seen in the latest scan. Returns count marked stale."""
    rows = conn.execute(
        "SELECT id, url FROM job_listings WHERE company_id = ? AND status = 'active'",
        (company_id,),
    ).fetchall()

    stale_count = 0
    for row in rows:
        if row["url"] not in active_urls:
            conn.execute(
                "UPDATE job_listings SET status = 'closed' WHERE id = ?",
                (row["id"],),
            )
            stale_count += 1

    if stale_count:
        conn.commit()
    return stale_count


def get_jobs(
    conn: sqlite3.Connection,
    company_id: int | None = None,
    status: str | None = None,
    min_relevance: float | None = None,
    limit: int = 50,
) -> list[sqlite3.Row]:
    """Get job listings with optional filters."""
    query = "SELECT j.*, c.name as company_name FROM job_listings j JOIN companies c ON j.company_id = c.id WHERE 1=1"
    params: list = []

    if company_id is not None:
        query += " AND j.company_id = ?"
        params.append(company_id)
    if status:
        query += " AND j.status = ?"
        params.append(status)
    if min_relevance is not None:
        query += " AND j.relevance_score >= ?"
        params.append(min_relevance)

    query += " ORDER BY j.relevance_score DESC, j.date_first_seen DESC LIMIT ?"
    params.append(limit)

    return conn.execute(query, params).fetchall()


def get_new_jobs_since(
    conn: sqlite3.Connection, since_date: str, min_relevance: float | None = None,
) -> list[sqlite3.Row]:
    """Get jobs first seen since a given date."""
    query = """SELECT j.*, c.name as company_name
               FROM job_listings j JOIN companies c ON j.company_id = c.id
               WHERE j.date_first_seen >= ?"""
    params: list = [since_date]

    if min_relevance is not None:
        query += " AND j.relevance_score >= ?"
        params.append(min_relevance)

    query += " ORDER BY j.relevance_score DESC"
    return conn.execute(query, params).fetchall()


def update_job_status(conn: sqlite3.Connection, job_id: int, status: str) -> bool:
    """Update a job's status (active, closed, applied, ignored). Returns True if found."""
    cursor = conn.execute(
        "UPDATE job_listings SET status = ? WHERE id = ?",
        (status, job_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def get_job_by_id(conn: sqlite3.Connection, job_id: int) -> sqlite3.Row | None:
    """Get a single job by ID with company name."""
    return conn.execute(
        """SELECT j.*, c.name as company_name
           FROM job_listings j JOIN companies c ON j.company_id = c.id
           WHERE j.id = ?""",
        (job_id,),
    ).fetchone()
