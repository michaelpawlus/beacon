"""Media log — track videos, podcasts, and articles with personal reactions."""

import json
import sqlite3


def add_media(
    conn: sqlite3.Connection,
    title: str,
    source_type: str,
    url: str | None = None,
    creator: str | None = None,
    platform: str | None = None,
    date_consumed: str | None = None,
    rating: int | None = None,
    tags: list[str] | None = None,
    key_takeaways: str | None = None,
    personal_reaction: str | None = None,
    team_shareable: bool = False,
    share_note: str | None = None,
    why_it_matters: str | None = None,
    key_quotes: list[str] | None = None,
    share_category: str | None = None,
) -> int:
    """Insert a media log entry and return its ID."""
    cur = conn.execute(
        """INSERT INTO media_log
           (title, url, source_type, creator, platform, date_consumed,
            rating, tags, key_takeaways, personal_reaction,
            team_shareable, share_note, why_it_matters, key_quotes, share_category)
           VALUES (?, ?, ?, ?, ?, COALESCE(?, date('now')), ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            title,
            url,
            source_type,
            creator,
            platform,
            date_consumed,
            rating,
            json.dumps(tags) if tags else None,
            key_takeaways,
            personal_reaction,
            1 if team_shareable else 0,
            share_note,
            why_it_matters,
            json.dumps(key_quotes) if key_quotes else None,
            share_category,
        ),
    )
    conn.commit()
    return cur.lastrowid


def list_media(
    conn: sqlite3.Connection,
    source_type: str | None = None,
    tag: str | None = None,
    min_rating: int | None = None,
    team_only: bool = False,
    since: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Query media log with optional filters (AND logic)."""
    clauses = []
    params: list = []

    if source_type:
        clauses.append("source_type = ?")
        params.append(source_type)
    if tag:
        clauses.append("tags LIKE ?")
        params.append(f"%{tag}%")
    if min_rating is not None:
        clauses.append("rating >= ?")
        params.append(min_rating)
    if team_only:
        clauses.append("team_shareable = 1")
    if since:
        clauses.append("date_consumed >= ?")
        params.append(since)
    if search:
        clauses.append("(title LIKE ? OR key_takeaways LIKE ? OR personal_reaction LIKE ? OR creator LIKE ?)")
        s = f"%{search}%"
        params.extend([s, s, s, s])

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    rows = conn.execute(
        f"SELECT * FROM media_log{where} ORDER BY date_consumed DESC, id DESC LIMIT ?",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_media(conn: sqlite3.Connection, media_id: int) -> dict | None:
    """Get a single media entry by ID."""
    row = conn.execute("SELECT * FROM media_log WHERE id = ?", (media_id,)).fetchone()
    return dict(row) if row else None


def update_media(
    conn: sqlite3.Connection,
    media_id: int,
    **kwargs,
) -> bool:
    """Update fields on a media entry. Returns True if row was found."""
    allowed = {
        "title", "url", "source_type", "creator", "platform", "date_consumed",
        "rating", "tags", "key_takeaways", "personal_reaction",
        "team_shareable", "share_note", "why_it_matters", "key_quotes",
        "share_category", "content_draft_id",
    }
    updates = {}
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if k in ("tags", "key_quotes") and isinstance(v, list):
                updates[k] = json.dumps(v)
            elif k == "team_shareable":
                updates[k] = 1 if v else 0
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
    params.append(media_id)

    cur = conn.execute(f"UPDATE media_log SET {set_clause} WHERE id = ?", params)
    conn.commit()
    return cur.rowcount > 0


def get_team_list(
    conn: sqlite3.Connection,
    source_type: str | None = None,
    tag: str | None = None,
    min_rating: int | None = None,
    since: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Get team-shareable media entries with only the relevant fields."""
    entries = list_media(
        conn,
        source_type=source_type,
        tag=tag,
        min_rating=min_rating,
        team_only=True,
        since=since,
        limit=limit,
    )
    return [
        {
            "id": e["id"],
            "title": e["title"],
            "url": e["url"],
            "source_type": e["source_type"],
            "creator": e["creator"],
            "platform": e["platform"],
            "date_consumed": e["date_consumed"],
            "rating": e["rating"],
            "tags": e["tags"],
            "share_note": e["share_note"],
            "why_it_matters": e.get("why_it_matters"),
            "key_quotes": e.get("key_quotes"),
            "share_category": e.get("share_category"),
        }
        for e in entries
    ]


def _flatten_json_field(value: str | None, separator: str = "; ") -> str:
    """Parse a JSON array string and join into a flat string."""
    if not value:
        return ""
    try:
        items = json.loads(value)
        if isinstance(items, list):
            return separator.join(str(i) for i in items)
    except (json.JSONDecodeError, TypeError):
        pass
    return value


def export_for_list(
    conn: sqlite3.Connection,
    source_type: str | None = None,
    tag: str | None = None,
    min_rating: int | None = None,
    since: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Export team-shareable media as flat dicts for Microsoft Lists / Power Automate.

    All JSON arrays are flattened to semicolon-separated strings so each row
    maps directly to a List column with no nested data.
    """
    entries = list_media(
        conn,
        source_type=source_type,
        tag=tag,
        min_rating=min_rating,
        team_only=True,
        since=since,
        limit=limit,
    )
    if category:
        entries = [e for e in entries if (e.get("share_category") or "").lower() == category.lower()]

    return [
        {
            "Title": e["title"],
            "URL": e.get("url") or "",
            "Type": e["source_type"],
            "Creator": e.get("creator") or "",
            "Category": e.get("share_category") or "",
            "WhyItMatters": e.get("why_it_matters") or "",
            "KeyPoints": e.get("key_takeaways") or "",
            "KeyQuotes": _flatten_json_field(e.get("key_quotes")),
            "Rating": e.get("rating") or "",
            "Date": e.get("date_consumed") or "",
            "Tags": _flatten_json_field(e.get("tags"), ", "),
            "ShareNote": e.get("share_note") or "",
        }
        for e in entries
    ]


def export_list_csv(entries: list[dict]) -> str:
    """Render export_for_list entries as CSV string."""
    import csv
    import io

    if not entries:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(entries[0].keys()))
    writer.writeheader()
    writer.writerows(entries)
    return output.getvalue()


def export_team_markdown(entries: list[dict]) -> str:
    """Render team-shareable entries as a markdown list."""
    if not entries:
        return "No team-shareable media found.\n"

    lines = ["# Recommended AI Content\n"]
    for e in entries:
        stars = f" {'⭐' * e['rating']}" if e.get("rating") else ""
        link = f"[{e['title']}]({e['url']})" if e.get("url") else e["title"]
        creator = f" — {e['creator']}" if e.get("creator") else ""
        lines.append(f"- {link}{creator}{stars}")
        if e.get("share_note"):
            lines.append(f"  {e['share_note']}")
        lines.append("")

    return "\n".join(lines)
