"""Speaker profile and presentation database operations."""

import json
import sqlite3
from datetime import datetime

# --- Presentations ---

def add_presentation(
    conn: sqlite3.Connection,
    title: str,
    abstract: str | None = None,
    key_points: list[str] | None = None,
    event_name: str | None = None,
    venue: str | None = None,
    event_url: str | None = None,
    date: str | None = None,
    duration_minutes: int | None = None,
    audience: str | None = None,
    status: str = "planned",
    slides_url: str | None = None,
    recording_url: str | None = None,
    co_presenters: list[str] | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> int:
    """Add a presentation. Returns the new ID."""
    cursor = conn.execute(
        """INSERT INTO presentations
           (title, abstract, key_points, event_name, venue, event_url, date,
            duration_minutes, audience, status, slides_url, recording_url,
            co_presenters, tags, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, abstract,
         json.dumps(key_points) if key_points else None,
         event_name, venue, event_url, date,
         duration_minutes, audience, status, slides_url, recording_url,
         json.dumps(co_presenters) if co_presenters else None,
         json.dumps(tags) if tags else None,
         notes),
    )
    conn.commit()
    return cursor.lastrowid


def get_presentations(conn: sqlite3.Connection, status: str | None = None) -> list[sqlite3.Row]:
    """Get presentations, optionally filtered by status."""
    query = "SELECT * FROM presentations"
    params: list = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY date DESC, created_at DESC"
    return conn.execute(query, params).fetchall()


def get_presentation_by_id(conn: sqlite3.Connection, pres_id: int) -> sqlite3.Row | None:
    """Get a single presentation by ID."""
    return conn.execute("SELECT * FROM presentations WHERE id = ?", (pres_id,)).fetchone()


def get_upcoming_presentations(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get upcoming presentations (planned/accepted with date >= today)."""
    today = datetime.now().strftime("%Y-%m-%d")
    return conn.execute(
        """SELECT * FROM presentations
           WHERE status IN ('planned', 'accepted') AND date >= ?
           ORDER BY date ASC""",
        (today,),
    ).fetchall()


def update_presentation(conn: sqlite3.Connection, pres_id: int, **kwargs) -> bool:
    """Update a presentation. Returns True if found."""
    if not kwargs:
        return False
    json_fields = {"key_points", "co_presenters", "tags"}
    sets = []
    params = []
    for key, value in kwargs.items():
        sets.append(f"{key} = ?")
        if key in json_fields and isinstance(value, list):
            params.append(json.dumps(value))
        else:
            params.append(value)
    sets.append("updated_at = datetime('now')")
    params.append(pres_id)
    cursor = conn.execute(
        f"UPDATE presentations SET {', '.join(sets)} WHERE id = ?", params,
    )
    conn.commit()
    return cursor.rowcount > 0


def delete_presentation(conn: sqlite3.Connection, pres_id: int) -> bool:
    """Delete a presentation. Returns True if found."""
    cursor = conn.execute("DELETE FROM presentations WHERE id = ?", (pres_id,))
    conn.commit()
    return cursor.rowcount > 0


# --- Speaker Profile ---

def get_speaker_profile(conn: sqlite3.Connection) -> sqlite3.Row | None:
    """Get the speaker profile (single row)."""
    return conn.execute("SELECT * FROM speaker_profile WHERE id = 1").fetchone()


def upsert_speaker_profile(
    conn: sqlite3.Connection,
    headshot_path: str | None = None,
    short_bio: str | None = None,
    long_bio: str | None = None,
) -> None:
    """Create or update the speaker profile. Only provided fields are changed."""
    existing = get_speaker_profile(conn)
    if existing:
        sets = ["updated_at = datetime('now')"]
        params: list = []
        if headshot_path is not None:
            sets.append("headshot_path = ?")
            params.append(headshot_path)
        if short_bio is not None:
            sets.append("short_bio = ?")
            params.append(short_bio)
        if long_bio is not None:
            sets.append("long_bio = ?")
            params.append(long_bio)
        if len(sets) > 1:
            conn.execute(f"UPDATE speaker_profile SET {', '.join(sets)} WHERE id = 1", params)
            conn.commit()
    else:
        conn.execute(
            """INSERT INTO speaker_profile (id, headshot_path, short_bio, long_bio)
               VALUES (1, ?, ?, ?)""",
            (headshot_path, short_bio, long_bio),
        )
        conn.commit()


def set_headshot(conn: sqlite3.Connection, path: str) -> None:
    """Set the headshot image path."""
    upsert_speaker_profile(conn, headshot_path=path)


def set_bio(conn: sqlite3.Connection, short_bio: str, long_bio: str | None = None) -> None:
    """Set the speaker bio and record generation timestamp."""
    existing = get_speaker_profile(conn)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if existing:
        sets = ["short_bio = ?", "bio_generated_at = ?", "updated_at = datetime('now')"]
        params: list = [short_bio, now]
        if long_bio is not None:
            sets.append("long_bio = ?")
            params.append(long_bio)
        conn.execute(f"UPDATE speaker_profile SET {', '.join(sets)} WHERE id = 1", params)
        conn.commit()
    else:
        conn.execute(
            """INSERT INTO speaker_profile (id, short_bio, long_bio, bio_generated_at)
               VALUES (1, ?, ?, ?)""",
            (short_bio, long_bio, now),
        )
        conn.commit()
