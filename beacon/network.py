"""Networking — track events attended and professional contacts."""

import json
import sqlite3

# ── Events ─────────────────────────────────────────────────────────


def add_event(
    conn: sqlite3.Connection,
    name: str,
    organizer: str | None = None,
    event_type: str = "meetup",
    url: str | None = None,
    location: str | None = None,
    date: str | None = None,
    description: str | None = None,
    attendee_count: int | None = None,
    status: str = "upcoming",
    tags: list[str] | None = None,
    notes: str | None = None,
) -> int:
    """Insert a network event and return its ID."""
    cur = conn.execute(
        """INSERT INTO network_events
           (name, organizer, event_type, url, location, date, description,
            attendee_count, status, tags, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            name,
            organizer,
            event_type,
            url,
            location,
            date,
            description,
            attendee_count,
            status,
            json.dumps(tags) if tags else None,
            notes,
        ),
    )
    conn.commit()
    return cur.lastrowid


def list_events(
    conn: sqlite3.Connection,
    status: str | None = None,
    event_type: str | None = None,
    since: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Query events with optional filters (AND logic)."""
    clauses = []
    params: list = []

    if status:
        clauses.append("status = ?")
        params.append(status)
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if since:
        clauses.append("date >= ?")
        params.append(since)
    if search:
        clauses.append("(name LIKE ? OR organizer LIKE ? OR description LIKE ? OR notes LIKE ?)")
        s = f"%{search}%"
        params.extend([s, s, s, s])

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    rows = conn.execute(
        f"SELECT * FROM network_events{where} ORDER BY date DESC, id DESC LIMIT ?",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_event(conn: sqlite3.Connection, event_id: int) -> dict | None:
    """Get a single event by ID."""
    row = conn.execute("SELECT * FROM network_events WHERE id = ?", (event_id,)).fetchone()
    return dict(row) if row else None


def update_event(conn: sqlite3.Connection, event_id: int, **kwargs) -> bool:
    """Update fields on an event. Returns True if row was found."""
    allowed = {
        "name", "organizer", "event_type", "url", "location", "date",
        "description", "attendee_count", "status", "tags", "notes",
    }
    updates = {}
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if k == "tags" and isinstance(v, list):
                updates[k] = json.dumps(v)
            else:
                updates[k] = v

    if not updates:
        return False

    updates["updated_at"] = "datetime('now')"
    set_clause = ", ".join(
        f"{k} = datetime('now')" if k == "updated_at" else f"{k} = ?"
        for k in updates
    )
    params = [v for k, v in updates.items() if k != "updated_at"]
    params.append(event_id)

    cur = conn.execute(f"UPDATE network_events SET {set_clause} WHERE id = ?", params)
    conn.commit()
    return cur.rowcount > 0


def get_event_contacts(conn: sqlite3.Connection, event_id: int) -> list[dict]:
    """Get all contacts linked to an event with join-table details."""
    rows = conn.execute(
        """SELECT nc.*, nce.topics_discussed, nce.follow_up, nce.followed_up, nce.notes AS link_notes
           FROM network_contacts nc
           JOIN network_contact_events nce ON nc.id = nce.contact_id
           WHERE nce.event_id = ?
           ORDER BY nc.priority DESC, nc.name""",
        (event_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Contacts ───────────────────────────────────────────────────────


def add_contact(
    conn: sqlite3.Connection,
    name: str,
    title: str | None = None,
    company: str | None = None,
    company_id: int | None = None,
    email: str | None = None,
    linkedin_url: str | None = None,
    bio: str | None = None,
    interests: list[str] | None = None,
    priority: int = 0,
    notes: str | None = None,
) -> int:
    """Insert a network contact and return its ID."""
    cur = conn.execute(
        """INSERT INTO network_contacts
           (name, title, company, company_id, email, linkedin_url, bio,
            interests, priority, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            name,
            title,
            company,
            company_id,
            email,
            linkedin_url,
            bio,
            json.dumps(interests) if interests else None,
            priority,
            notes,
        ),
    )
    conn.commit()
    return cur.lastrowid


def list_contacts(
    conn: sqlite3.Connection,
    company: str | None = None,
    event_id: int | None = None,
    min_priority: int | None = None,
    search: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Query contacts with optional filters (AND logic)."""
    clauses = []
    params: list = []
    join = ""

    if event_id is not None:
        join = " JOIN network_contact_events nce ON nc.id = nce.contact_id"
        clauses.append("nce.event_id = ?")
        params.append(event_id)
    if company:
        clauses.append("nc.company LIKE ?")
        params.append(f"%{company}%")
    if min_priority is not None:
        clauses.append("nc.priority >= ?")
        params.append(min_priority)
    if search:
        clauses.append("(nc.name LIKE ? OR nc.title LIKE ? OR nc.company LIKE ? OR nc.bio LIKE ? OR nc.notes LIKE ?)")
        s = f"%{search}%"
        params.extend([s, s, s, s, s])

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    rows = conn.execute(
        f"SELECT DISTINCT nc.* FROM network_contacts nc{join}{where} ORDER BY nc.priority DESC, nc.name LIMIT ?",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_contact(conn: sqlite3.Connection, contact_id: int) -> dict | None:
    """Get a single contact by ID."""
    row = conn.execute("SELECT * FROM network_contacts WHERE id = ?", (contact_id,)).fetchone()
    return dict(row) if row else None


def update_contact(conn: sqlite3.Connection, contact_id: int, **kwargs) -> bool:
    """Update fields on a contact. Returns True if row was found."""
    allowed = {
        "name", "title", "company", "company_id", "email", "linkedin_url",
        "bio", "interests", "priority", "notes",
    }
    updates = {}
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if k == "interests" and isinstance(v, list):
                updates[k] = json.dumps(v)
            else:
                updates[k] = v

    if not updates:
        return False

    updates["updated_at"] = "datetime('now')"
    set_clause = ", ".join(
        f"{k} = datetime('now')" if k == "updated_at" else f"{k} = ?"
        for k in updates
    )
    params = [v for k, v in updates.items() if k != "updated_at"]
    params.append(contact_id)

    cur = conn.execute(f"UPDATE network_contacts SET {set_clause} WHERE id = ?", params)
    conn.commit()
    return cur.rowcount > 0


def get_contact_events(conn: sqlite3.Connection, contact_id: int) -> list[dict]:
    """Get all events a contact has been linked to."""
    rows = conn.execute(
        """SELECT ne.*, nce.topics_discussed, nce.follow_up, nce.followed_up, nce.notes AS link_notes
           FROM network_events ne
           JOIN network_contact_events nce ON ne.id = nce.event_id
           WHERE nce.contact_id = ?
           ORDER BY ne.date DESC""",
        (contact_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Contact-Event Links ───────────────────────────────────────────


def link_contact_event(
    conn: sqlite3.Connection,
    contact_id: int,
    event_id: int,
    topics_discussed: str | None = None,
    follow_up: str | None = None,
    notes: str | None = None,
) -> int:
    """Link a contact to an event. Returns the link row ID."""
    cur = conn.execute(
        """INSERT OR REPLACE INTO network_contact_events
           (contact_id, event_id, topics_discussed, follow_up, notes)
           VALUES (?, ?, ?, ?, ?)""",
        (contact_id, event_id, topics_discussed, follow_up, notes),
    )
    conn.commit()
    return cur.lastrowid


def update_link(conn: sqlite3.Connection, contact_id: int, event_id: int, **kwargs) -> bool:
    """Update fields on a contact-event link."""
    allowed = {"topics_discussed", "follow_up", "followed_up", "notes"}
    updates = {}
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if k == "followed_up":
                updates[k] = 1 if v else 0
            else:
                updates[k] = v

    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values())
    params.extend([contact_id, event_id])

    cur = conn.execute(
        f"UPDATE network_contact_events SET {set_clause} WHERE contact_id = ? AND event_id = ?",
        params,
    )
    conn.commit()
    return cur.rowcount > 0


# ── Prep helpers ───────────────────────────────────────────────────


def prep_event(conn: sqlite3.Connection, event_id: int) -> dict | None:
    """Gather event + contacts + company cross-references for event prep."""
    event = get_event(conn, event_id)
    if not event:
        return None

    contacts = get_event_contacts(conn, event_id)

    # Cross-reference contacts whose companies are in the beacon DB
    enriched = []
    for c in contacts:
        entry = dict(c)
        if c.get("company_id"):
            company_row = conn.execute(
                "SELECT name, ai_first_score, tier, description FROM companies WHERE id = ?",
                (c["company_id"],),
            ).fetchone()
            if company_row:
                entry["beacon_company"] = dict(company_row)
        elif c.get("company"):
            company_row = conn.execute(
                "SELECT id, name, ai_first_score, tier, description FROM companies WHERE name LIKE ?",
                (f"%{c['company']}%",),
            ).fetchone()
            if company_row:
                entry["beacon_company"] = dict(company_row)
        enriched.append(entry)

    # Sort: contacts with beacon company matches first, then by priority
    enriched.sort(key=lambda x: (0 if x.get("beacon_company") else 1, -(x.get("priority") or 0)))

    return {
        "event": event,
        "contacts": enriched,
        "total_contacts": len(enriched),
        "beacon_matches": sum(1 for c in enriched if c.get("beacon_company")),
    }
