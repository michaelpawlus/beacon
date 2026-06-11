"""STAR+Reflection interview story bank (#30).

Stories are the narrative layer of the career OS: distilled from wins
(`beacon career win promote`) or captured directly, tagged by role archetype
and interview dimension, and surfaced per-job by `beacon profile story suggest`.

The Reflection field is the explicit seniority signal — "junior candidates
describe what happened, senior candidates extract lessons" — so a story
without a reflection stays `draft` and cannot be marked `polished`.
"""

import json
import sqlite3

from beacon.research.archetypes import classify_job, is_valid_archetype

# Interview dimensions the coverage report checks for polished-story coverage.
CORE_TAGS = ("leadership", "ambiguity", "failure", "scope-cut", "cross-functional")

STORY_STATUSES = ("draft", "polished", "retired")

STAR_FIELDS = ("situation", "task", "action", "result", "reflection")


def _validate_archetypes(archetypes: list[str] | None) -> None:
    for key in archetypes or []:
        if not is_valid_archetype(key):
            raise ValueError(f"Unknown archetype {key!r}. See `beacon job archetype --list`.")


def _resolve_status(status: str | None, reflection: str | None) -> str:
    """Apply the reflection gate: no reflection → draft, regardless of intent."""
    if status is not None and status not in STORY_STATUSES:
        raise ValueError(f"Unknown status {status!r}. Valid: {', '.join(STORY_STATUSES)}")
    if status == "polished" and not reflection:
        raise ValueError("A story cannot be polished without a reflection — that's the gate.")
    if status is None:
        return "polished" if reflection else "draft"
    return status


def add_story(
    conn: sqlite3.Connection,
    title: str,
    situation: str | None = None,
    task: str | None = None,
    action: str | None = None,
    result: str | None = None,
    reflection: str | None = None,
    archetypes: list[str] | None = None,
    tags: list[str] | None = None,
    linked_work_id: int | None = None,
    win_id: int | None = None,
    status: str | None = None,
) -> int:
    """Insert a story and return its ID. Status defaults via the reflection gate."""
    _validate_archetypes(archetypes)
    resolved = _resolve_status(status, reflection)

    cur = conn.execute(
        """INSERT INTO interview_stories
           (title, situation, task, action, result, reflection,
            archetypes, tags, linked_work_id, win_id, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            title,
            situation,
            task,
            action,
            result,
            reflection,
            json.dumps(archetypes) if archetypes else None,
            json.dumps(tags) if tags else None,
            linked_work_id,
            win_id,
            resolved,
        ),
    )
    conn.commit()
    return cur.lastrowid


def list_stories(
    conn: sqlite3.Connection,
    tag: str | None = None,
    archetype: str | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Query stories with optional filters (AND logic)."""
    clauses = []
    params: list = []

    if tag:
        clauses.append("tags LIKE ?")
        params.append(f"%{tag}%")
    if archetype:
        clauses.append("archetypes LIKE ?")
        params.append(f"%{archetype}%")
    if status:
        clauses.append("status = ?")
        params.append(status)
    if search:
        clauses.append(
            "(title LIKE ? OR situation LIKE ? OR action LIKE ? OR result LIKE ? OR reflection LIKE ?)"
        )
        s = f"%{search}%"
        params.extend([s] * 5)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    rows = conn.execute(
        f"SELECT * FROM interview_stories{where} ORDER BY updated_at DESC, id DESC LIMIT ?",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_story(conn: sqlite3.Connection, story_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM interview_stories WHERE id = ?", (story_id,)).fetchone()
    return dict(row) if row else None


def update_story(conn: sqlite3.Connection, story_id: int, **kwargs) -> bool:
    """Update fields on a story. Returns True if the row was found.

    Adding a reflection to a draft auto-promotes it to polished unless an
    explicit status is passed; setting status='polished' without a reflection
    (existing or incoming) raises.
    """
    existing = get_story(conn, story_id)
    if not existing:
        return False

    allowed = {
        "title", "situation", "task", "action", "result", "reflection",
        "archetypes", "tags", "target_role_ids", "linked_work_id", "win_id", "status",
    }
    updates = {}
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if k in ("archetypes", "tags", "target_role_ids") and isinstance(v, list):
                if k == "archetypes":
                    _validate_archetypes(v)
                updates[k] = json.dumps(v)
            else:
                updates[k] = v

    if not updates:
        return False

    reflection = updates.get("reflection", existing.get("reflection"))
    if "status" in updates:
        updates["status"] = _resolve_status(updates["status"], reflection)
    elif updates.get("reflection") and existing.get("status") == "draft":
        updates["status"] = "polished"

    set_clause = ", ".join(f"{k} = ?" for k in updates) + ", updated_at = datetime('now')"
    params = list(updates.values())
    params.append(story_id)
    conn.execute(f"UPDATE interview_stories SET {set_clause} WHERE id = ?", params)
    conn.commit()
    return True


def promote_win(
    conn: sqlite3.Connection,
    win_id: int,
    reflection: str | None = None,
    title: str | None = None,
) -> int:
    """Distill a win into a draft story: prefill STAR from the win, Reflection is yours.

    Prefill mapping: task ← win title, situation ← description, result ← impact
    + metrics. Action is left empty for `story update` (or the interactive
    prompt in the CLI) — the win log records *what*, the story needs *how*.
    Raises ValueError if the win doesn't exist or was already promoted.
    """
    win = conn.execute("SELECT * FROM wins WHERE id = ?", (win_id,)).fetchone()
    if not win:
        raise ValueError(f"Win {win_id} not found")
    if win["story_id"]:
        raise ValueError(f"Win {win_id} already promoted to story {win['story_id']}")

    metrics = []
    try:
        metrics = json.loads(win["metrics"] or "[]")
    except (json.JSONDecodeError, TypeError):
        pass
    result_parts = [p for p in [win["impact"], "; ".join(str(m) for m in metrics)] if p]

    tags = None
    try:
        parsed = json.loads(win["tags"] or "null")
        if isinstance(parsed, list) and parsed:
            tags = parsed
    except (json.JSONDecodeError, TypeError):
        pass

    story_id = add_story(
        conn,
        title=title or win["title"],
        situation=win["description"],
        task=win["title"],
        result=". ".join(result_parts) or None,
        reflection=reflection,
        tags=tags,
        linked_work_id=win["work_experience_id"],
        win_id=win_id,
    )
    conn.execute(
        "UPDATE wins SET story_id = ?, updated_at = datetime('now') WHERE id = ?",
        (story_id, win_id),
    )
    conn.commit()
    return story_id


def _story_text(story: dict) -> str:
    parts = [story.get(f) or "" for f in ("title", "situation", "task", "action", "result")]
    tags = story.get("tags") or ""
    return " ".join(parts + [tags]).lower()


def suggest_stories(
    conn: sqlite3.Connection,
    job_row: sqlite3.Row,
    top: int = 8,
    mark_used: bool = False,
) -> dict:
    """Rank non-retired stories for a job by archetype match + requirement overlap.

    Score = 3.0 archetype match + 1.0 per matched requirement term (cap 5)
    + 1.0 polished bonus. Returns {"job_archetype": ..., "suggestions": [...]}.
    """
    from beacon.research.job_fit import get_or_extract_requirements

    job_archetype = job_row["archetype"] if "archetype" in job_row.keys() else None
    if not job_archetype:
        description = job_row["description_text"] if "description_text" in job_row.keys() else ""
        job_archetype = classify_job(job_row["title"], description or "")["archetype"]

    requirements = get_or_extract_requirements(conn, job_row)
    terms = {
        t.lower()
        for t in (
            requirements.get("required_skills", [])
            + requirements.get("preferred_skills", [])
            + requirements.get("keywords", [])
        )
        if t
    }

    stories = [s for s in list_stories(conn, limit=500) if s["status"] != "retired"]
    scored = []
    for story in stories:
        text = _story_text(story)
        matched = sorted(t for t in terms if t in text)
        overlap = min(len(matched), 5)

        archetype_hit = False
        try:
            story_archetypes = json.loads(story.get("archetypes") or "[]")
        except (json.JSONDecodeError, TypeError):
            story_archetypes = []
        if job_archetype and job_archetype in story_archetypes:
            archetype_hit = True

        score = (3.0 if archetype_hit else 0.0) + float(overlap)
        if story["status"] == "polished":
            score += 1.0
        if score <= 0:
            continue

        reasons = []
        if archetype_hit:
            reasons.append(f"archetype:{job_archetype}")
        reasons.extend(f"term:{t}" for t in matched)
        scored.append(
            {
                "id": story["id"],
                "title": story["title"],
                "status": story["status"],
                "score": round(score, 1),
                "reasons": reasons,
            }
        )

    scored.sort(key=lambda s: (-s["score"], s["id"]))
    suggestions = scored[:top]

    if mark_used and suggestions:
        ids = [s["id"] for s in suggestions]
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE interview_stories SET times_used = times_used + 1, "
            f"last_used_at = datetime('now') WHERE id IN ({placeholders})",
            ids,
        )
        conn.commit()

    return {"job_archetype": job_archetype, "suggestions": suggestions}


def coverage(conn: sqlite3.Connection) -> dict:
    """Coverage of interview dimensions (CORE_TAGS) and archetypes by polished stories.

    Per-target-role coverage lands with #43 (role_targets); until then the
    matrix is dimensions × archetypes over the whole bank.
    """
    stories = list_stories(conn, limit=1000)
    polished = [s for s in stories if s["status"] == "polished"]

    def _parse(value):
        try:
            parsed = json.loads(value or "[]")
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    by_tag = {t: 0 for t in CORE_TAGS}
    by_archetype: dict[str, int] = {}
    for s in polished:
        for t in _parse(s.get("tags")):
            if t in by_tag:
                by_tag[t] += 1
        for a in _parse(s.get("archetypes")):
            by_archetype[a] = by_archetype.get(a, 0) + 1

    return {
        "total": len(stories),
        "polished": len(polished),
        "draft": sum(1 for s in stories if s["status"] == "draft"),
        "by_tag": by_tag,
        "by_archetype": by_archetype,
        "uncovered_tags": [t for t, n in by_tag.items() if n == 0],
    }
