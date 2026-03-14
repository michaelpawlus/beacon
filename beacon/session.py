"""Session logging — capture Claude Code sessions as structured notes."""

import json
import os
import re
import sqlite3
from pathlib import Path


def slugify(text: str, max_length: int = 50) -> str:
    """Convert text to a URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:max_length].rstrip("-")


def generate_session_note(
    title: str,
    summary: str,
    project: str = "beacon",
    challenges: list[str] | None = None,
    technologies: list[str] | None = None,
    impact: str | None = None,
    tags: list[str] | None = None,
    session_date: str | None = None,
    duration_estimate: str | None = None,
) -> str:
    """Build an Obsidian markdown note with frontmatter."""
    all_tags = ["session-log", project] + (tags or [])
    # Deduplicate while preserving order
    seen = set()
    unique_tags = []
    for t in all_tags:
        if t not in seen:
            seen.add(t)
            unique_tags.append(t)

    lines = [
        "---",
        f"date: {session_date or ''}",
        "type: session-log",
        f"project: {project}",
        f"tags: [{', '.join(unique_tags)}]",
        "---",
        "",
        f"# {title}",
        "",
        "## Summary",
        summary,
    ]

    if challenges:
        lines += ["", "## Challenges & Solutions"]
        for c in challenges:
            lines.append(f"- {c}")

    if technologies:
        lines += ["", "## Technologies & Patterns"]
        for t in technologies:
            lines.append(f"- {t}")

    if impact:
        lines += ["", "## Impact", impact]

    lines += [
        "",
        "## Details",
        f"- **Project:** {project}",
        f"- **Date:** {session_date or ''}",
        f"- **Duration:** {duration_estimate or ''}",
        "",
    ]

    return "\n".join(lines)


def write_session_note(content: str, session_date: str, slug: str) -> str:
    """Write note to $OBSIDIAN_VAULT_PATH/claude-sessions/. Returns the file path."""
    vault = os.environ.get("OBSIDIAN_VAULT_PATH", "")
    if not vault:
        raise RuntimeError("OBSIDIAN_VAULT_PATH environment variable is not set")

    out_dir = Path(vault) / "claude-sessions"
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{session_date}-{slug}.md"
    filepath = out_dir / filename
    filepath.write_text(content)
    return str(filepath)


def save_session_to_db(
    conn: sqlite3.Connection,
    title: str,
    summary: str,
    project: str = "beacon",
    challenges: list[str] | None = None,
    technologies: list[str] | None = None,
    impact: str | None = None,
    tags: list[str] | None = None,
    transcript_path: str | None = None,
    obsidian_path: str | None = None,
    duration_estimate: str | None = None,
    session_date: str | None = None,
) -> int:
    """Insert a session record and return its ID."""
    cur = conn.execute(
        """INSERT INTO sessions
           (title, project, summary, challenges, technologies, impact,
            tags, transcript_path, obsidian_path, duration_estimate, session_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, date('now')))""",
        (
            title,
            project,
            summary,
            json.dumps(challenges) if challenges else None,
            json.dumps(technologies) if technologies else None,
            impact,
            json.dumps(tags) if tags else None,
            transcript_path,
            obsidian_path,
            duration_estimate,
            session_date,
        ),
    )
    conn.commit()
    return cur.lastrowid


def list_sessions(
    conn: sqlite3.Connection,
    project: str | None = None,
    tag: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Query sessions with optional filters."""
    clauses = []
    params: list = []

    if project:
        clauses.append("project = ?")
        params.append(project)
    if tag:
        clauses.append("tags LIKE ?")
        params.append(f"%{tag}%")

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    rows = conn.execute(
        f"SELECT * FROM sessions{where} ORDER BY session_date DESC LIMIT ?",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_session(conn: sqlite3.Connection, session_id: int) -> dict | None:
    """Get a single session by ID."""
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else None
