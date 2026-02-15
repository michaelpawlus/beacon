"""Content database operations for Beacon Phase 4.

CRUD operations for content_drafts, content_calendar, and accomplishments tables.
"""

import json
import sqlite3


# --- Content Drafts ---

def add_content_draft(
    conn: sqlite3.Connection,
    content_type: str,
    platform: str,
    title: str,
    body: str,
    status: str = "draft",
    metadata: dict | None = None,
) -> int:
    """Add a content draft. Returns the new ID."""
    cursor = conn.execute(
        """INSERT INTO content_drafts
           (content_type, platform, title, body, status, metadata)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (content_type, platform, title, body, status,
         json.dumps(metadata) if metadata else None),
    )
    conn.commit()
    return cursor.lastrowid


def get_content_drafts(
    conn: sqlite3.Connection,
    platform: str | None = None,
    status: str | None = None,
    content_type: str | None = None,
) -> list[sqlite3.Row]:
    """Get content drafts with optional filters."""
    query = "SELECT * FROM content_drafts WHERE 1=1"
    params: list = []
    if platform:
        query += " AND platform = ?"
        params.append(platform)
    if status:
        query += " AND status = ?"
        params.append(status)
    if content_type:
        query += " AND content_type = ?"
        params.append(content_type)
    query += " ORDER BY updated_at DESC"
    return conn.execute(query, params).fetchall()


def get_content_draft_by_id(conn: sqlite3.Connection, draft_id: int) -> sqlite3.Row | None:
    """Get a single content draft by ID."""
    return conn.execute("SELECT * FROM content_drafts WHERE id = ?", (draft_id,)).fetchone()


def update_content_draft(conn: sqlite3.Connection, draft_id: int, **kwargs) -> bool:
    """Update a content draft. Returns True if found."""
    if not kwargs:
        return False
    json_fields = {"metadata"}
    sets = []
    params = []
    for key, value in kwargs.items():
        sets.append(f"{key} = ?")
        if key in json_fields and isinstance(value, dict):
            params.append(json.dumps(value))
        else:
            params.append(value)
    sets.append("updated_at = datetime('now')")
    params.append(draft_id)
    cursor = conn.execute(
        f"UPDATE content_drafts SET {', '.join(sets)} WHERE id = ?", params,
    )
    conn.commit()
    return cursor.rowcount > 0


def delete_content_draft(conn: sqlite3.Connection, draft_id: int) -> bool:
    """Delete a content draft. Returns True if found."""
    cursor = conn.execute("DELETE FROM content_drafts WHERE id = ?", (draft_id,))
    conn.commit()
    return cursor.rowcount > 0


def publish_content_draft(conn: sqlite3.Connection, draft_id: int, url: str | None = None) -> bool:
    """Mark a draft as published with optional URL and timestamp."""
    from datetime import datetime
    cursor = conn.execute(
        """UPDATE content_drafts
           SET status = 'published', published_url = ?, published_at = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (url, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), draft_id),
    )
    conn.commit()
    return cursor.rowcount > 0


# --- Content Calendar ---

def add_calendar_entry(
    conn: sqlite3.Connection,
    title: str,
    platform: str,
    content_type: str,
    topic: str | None = None,
    target_date: str | None = None,
    status: str = "idea",
    draft_id: int | None = None,
    notes: str | None = None,
) -> int:
    """Add a content calendar entry. Returns the new ID."""
    cursor = conn.execute(
        """INSERT INTO content_calendar
           (title, platform, content_type, topic, target_date, status, draft_id, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, platform, content_type, topic, target_date, status, draft_id, notes),
    )
    conn.commit()
    return cursor.lastrowid


def get_calendar_entries(
    conn: sqlite3.Connection,
    platform: str | None = None,
    status: str | None = None,
) -> list[sqlite3.Row]:
    """Get calendar entries with optional filters."""
    query = "SELECT * FROM content_calendar WHERE 1=1"
    params: list = []
    if platform:
        query += " AND platform = ?"
        params.append(platform)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY target_date ASC, created_at DESC"
    return conn.execute(query, params).fetchall()


def get_calendar_entry_by_id(conn: sqlite3.Connection, entry_id: int) -> sqlite3.Row | None:
    """Get a single calendar entry by ID."""
    return conn.execute("SELECT * FROM content_calendar WHERE id = ?", (entry_id,)).fetchone()


def update_calendar_entry(conn: sqlite3.Connection, entry_id: int, **kwargs) -> bool:
    """Update a calendar entry. Returns True if found."""
    if not kwargs:
        return False
    sets = []
    params = []
    for key, value in kwargs.items():
        sets.append(f"{key} = ?")
        params.append(value)
    sets.append("updated_at = datetime('now')")
    params.append(entry_id)
    cursor = conn.execute(
        f"UPDATE content_calendar SET {', '.join(sets)} WHERE id = ?", params,
    )
    conn.commit()
    return cursor.rowcount > 0


def delete_calendar_entry(conn: sqlite3.Connection, entry_id: int) -> bool:
    """Delete a calendar entry. Returns True if found."""
    cursor = conn.execute("DELETE FROM content_calendar WHERE id = ?", (entry_id,))
    conn.commit()
    return cursor.rowcount > 0


# --- Accomplishments ---

def add_accomplishment(
    conn: sqlite3.Connection,
    raw_statement: str,
    work_experience_id: int | None = None,
    context: str | None = None,
    action: str | None = None,
    result: str | None = None,
    metrics: str | None = None,
    technologies: str | None = None,
    stakeholders: str | None = None,
    timeline: str | None = None,
    challenges: str | None = None,
    learning: str | None = None,
    content_angles: str | None = None,
) -> int:
    """Add an accomplishment record. Returns the new ID."""
    cursor = conn.execute(
        """INSERT INTO accomplishments
           (work_experience_id, raw_statement, context, action, result,
            metrics, technologies, stakeholders, timeline, challenges,
            learning, content_angles)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (work_experience_id, raw_statement, context, action, result,
         metrics, technologies, stakeholders, timeline, challenges,
         learning, content_angles),
    )
    conn.commit()
    return cursor.lastrowid


def get_accomplishments(
    conn: sqlite3.Connection,
    work_experience_id: int | None = None,
) -> list[sqlite3.Row]:
    """Get accomplishments, optionally filtered by work experience."""
    query = "SELECT * FROM accomplishments WHERE 1=1"
    params: list = []
    if work_experience_id is not None:
        query += " AND work_experience_id = ?"
        params.append(work_experience_id)
    query += " ORDER BY created_at DESC"
    return conn.execute(query, params).fetchall()


def get_accomplishment_by_id(conn: sqlite3.Connection, acc_id: int) -> sqlite3.Row | None:
    """Get a single accomplishment by ID."""
    return conn.execute("SELECT * FROM accomplishments WHERE id = ?", (acc_id,)).fetchone()


def update_accomplishment(conn: sqlite3.Connection, acc_id: int, **kwargs) -> bool:
    """Update an accomplishment. Returns True if found."""
    if not kwargs:
        return False
    sets = []
    params = []
    for key, value in kwargs.items():
        sets.append(f"{key} = ?")
        params.append(value)
    sets.append("updated_at = datetime('now')")
    params.append(acc_id)
    cursor = conn.execute(
        f"UPDATE accomplishments SET {', '.join(sets)} WHERE id = ?", params,
    )
    conn.commit()
    return cursor.rowcount > 0


def delete_accomplishment(conn: sqlite3.Connection, acc_id: int) -> bool:
    """Delete an accomplishment. Returns True if found."""
    cursor = conn.execute("DELETE FROM accomplishments WHERE id = ?", (acc_id,))
    conn.commit()
    return cursor.rowcount > 0
