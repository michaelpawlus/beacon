"""Career OS — win/evidence log for brag-document discipline.

Beacon v2's center of gravity: wins are logged as they happen at the current
job, accumulate into the evidence base that feeds interview stories (#30),
aspirational-role fit tracking, and the periodic brag-document review.

Categories deliberately encode the value-overhang thesis: `adoption` and
`enablement` wins are diffusion work (closing the gap between model capability
and realized business value); `delivery` wins are build work. The review
surfaces the mix so the balance is a choice, not an accident.
"""

import json
import re
import sqlite3
from datetime import date, timedelta

WIN_CATEGORIES = (
    "delivery",
    "adoption",
    "enablement",
    "relationship",
    "revenue",
    "learning",
    "visibility",
    "process",
)

DIFFUSION_CATEGORIES = ("adoption", "enablement", "relationship")

VISIBILITY_LEVELS = ("private", "team", "public")


def resolve_since(since: str | None) -> str | None:
    """Resolve a --since value to an ISO date. Accepts YYYY-MM-DD or Nd (e.g. 30d)."""
    if not since:
        return None
    m = re.fullmatch(r"(\d+)d", since.strip())
    if m:
        return (date.today() - timedelta(days=int(m.group(1)))).isoformat()
    return since


def add_win(
    conn: sqlite3.Connection,
    title: str,
    category: str | None = None,
    description: str | None = None,
    impact: str | None = None,
    metrics: list[str] | None = None,
    stakeholders: list[str] | None = None,
    technologies: list[str] | None = None,
    tags: list[str] | None = None,
    win_date: str | None = None,
    work_experience_id: int | None = None,
    session_id: int | None = None,
    project_id: int | None = None,
    visibility: str = "private",
) -> int:
    """Insert a win and return its ID. Raises ValueError on bad category/visibility."""
    if category is not None and category not in WIN_CATEGORIES:
        raise ValueError(f"Unknown category {category!r}. Valid: {', '.join(WIN_CATEGORIES)}")
    if visibility not in VISIBILITY_LEVELS:
        raise ValueError(f"Unknown visibility {visibility!r}. Valid: {', '.join(VISIBILITY_LEVELS)}")

    cur = conn.execute(
        """INSERT INTO wins
           (title, win_date, category, description, impact, metrics, stakeholders,
            technologies, tags, work_experience_id, session_id, project_id, visibility)
           VALUES (?, COALESCE(?, date('now')), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            title,
            win_date,
            category,
            description,
            impact,
            json.dumps(metrics) if metrics else None,
            json.dumps(stakeholders) if stakeholders else None,
            json.dumps(technologies) if technologies else None,
            json.dumps(tags) if tags else None,
            work_experience_id,
            session_id,
            project_id,
            visibility,
        ),
    )
    conn.commit()
    return cur.lastrowid


def list_wins(
    conn: sqlite3.Connection,
    category: str | None = None,
    since: str | None = None,
    untold: bool = False,
    visibility: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Query wins with optional filters (AND logic). `untold` = not yet promoted to a story."""
    clauses = []
    params: list = []

    if category:
        clauses.append("category = ?")
        params.append(category)
    if since:
        clauses.append("win_date >= ?")
        params.append(resolve_since(since))
    if untold:
        clauses.append("story_id IS NULL")
    if visibility:
        clauses.append("visibility = ?")
        params.append(visibility)
    if search:
        clauses.append("(title LIKE ? OR description LIKE ? OR impact LIKE ?)")
        s = f"%{search}%"
        params.extend([s, s, s])

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    rows = conn.execute(
        f"SELECT * FROM wins{where} ORDER BY win_date DESC, id DESC LIMIT ?",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_win(conn: sqlite3.Connection, win_id: int) -> dict | None:
    """Get a single win by ID."""
    row = conn.execute("SELECT * FROM wins WHERE id = ?", (win_id,)).fetchone()
    return dict(row) if row else None


def category_mix(wins: list[dict]) -> dict:
    """Count wins per category, plus the delivery-vs-diffusion split."""
    counts: dict[str, int] = {}
    for w in wins:
        key = w.get("category") or "uncategorized"
        counts[key] = counts.get(key, 0) + 1
    diffusion = sum(counts.get(c, 0) for c in DIFFUSION_CATEGORIES)
    delivery = counts.get("delivery", 0)
    return {"by_category": counts, "diffusion": diffusion, "delivery": delivery}


def current_role(conn: sqlite3.Connection) -> dict | None:
    """The current work experience (end_date IS NULL), newest first."""
    row = conn.execute(
        "SELECT * FROM work_experiences WHERE end_date IS NULL ORDER BY start_date DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def _parse_json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else [parsed]
    except (json.JSONDecodeError, TypeError):
        return [value]


def target_progress(conn: sqlite3.Connection, since: str | None = None) -> dict:
    """The regular wins↔gaps check for the review: which wins in the window are
    evidence against target-demanded gaps, and which gaps to prioritize next."""
    from beacon.targets import (
        SNAPSHOT_STALE_DAYS,
        analyze_target_gaps,
        latest_snapshot_age_days,
        wins_closing_gaps,
    )

    analysis = analyze_target_gaps(conn)
    age = latest_snapshot_age_days(conn)
    return {
        "targets_analyzed": analysis["targets_analyzed"],
        "wins_closing_gaps": wins_closing_gaps(conn, since=resolve_since(since)),
        "next_gaps": analysis["gaps"][:5],
        "snapshot_age_days": age,
        "snapshot_stale": age is None or age > SNAPSHOT_STALE_DAYS,
    }


def render_review_markdown(
    wins: list[dict],
    since_label: str,
    role: dict | None = None,
    targets: dict | None = None,
) -> str:
    """Render the brag-document review as markdown."""
    today = date.today().isoformat()
    lines = [f"# Career Review — {today}", ""]
    if role:
        lines.append(f"**Role:** {role['title']} at {role['company']}")
    lines.append(f"**Window:** {since_label}")
    lines.append(f"**Wins logged:** {len(wins)}")
    lines.append("")

    if not wins:
        lines.append("No wins logged in this window. If the work happened, the evidence")
        lines.append("didn't — log it with `beacon career win add` before it fades.")
        return "\n".join(lines) + "\n"

    mix = category_mix(wins)
    lines.append("## Win Mix")
    lines.append("")
    for cat, count in sorted(mix["by_category"].items(), key=lambda kv: -kv[1]):
        lines.append(f"- {cat}: {count}")
    lines.append("")
    lines.append(
        f"Diffusion (adoption/enablement/relationship) vs delivery: "
        f"**{mix['diffusion']} vs {mix['delivery']}** — diffusion work is where the "
        f"value overhang closes; keep this ratio deliberate."
    )
    lines.append("")

    lines.append("## Wins")
    lines.append("")
    for w in wins:
        cat = f" `{w['category']}`" if w.get("category") else ""
        lines.append(f"### {w['title']}{cat}")
        lines.append("")
        lines.append(f"*{w.get('win_date', '')}*")
        if w.get("description"):
            lines.append("")
            lines.append(w["description"])
        if w.get("impact"):
            lines.append("")
            lines.append(f"**Impact:** {w['impact']}")
        metrics = _parse_json_list(w.get("metrics"))
        if metrics:
            lines.append("")
            lines.append("**Metrics:**")
            for m in metrics:
                lines.append(f"- {m}")
        stakeholders = _parse_json_list(w.get("stakeholders"))
        if stakeholders:
            lines.append("")
            lines.append(f"**Stakeholders:** {', '.join(str(s) for s in stakeholders)}")
        lines.append("")

    untold = [w for w in wins if not w.get("story_id")]
    strong_untold = [w for w in untold if _parse_json_list(w.get("metrics"))]
    if strong_untold:
        lines.append("## Untold Stories")
        lines.append("")
        lines.append("Wins with metrics but no interview story yet — promote while fresh:")
        for w in strong_untold:
            lines.append(f"- [{w['id']}] {w['title']}")
        lines.append("")

    if targets and targets.get("targets_analyzed"):
        lines.append("## Aspirational Targets — wins vs gaps")
        lines.append("")
        closing = targets.get("wins_closing_gaps") or []
        if closing:
            lines.append("Wins this window that are evidence against target gaps — get these")
            lines.append("onto the resume and into skills:")
            for w in closing:
                lines.append(f"- [{w['id']}] {w['title']} → {', '.join(w['gap_skills'])}")
        else:
            lines.append("No wins this window touched a target-demanded gap. The day job is")
            lines.append("drifting from the 2–4 year vector — pick work that closes a gap.")
        lines.append("")
        next_gaps = targets.get("next_gaps") or []
        if next_gaps:
            lines.append("Next gaps to prioritize (horizon-weighted):")
            for g in next_gaps:
                field = " *(field-validated)*" if g.get("field_observed") else ""
                lines.append(
                    f"- **{g['skill_name']}** — {g['demand_count']} targets, priority {g['priority']}{field}"
                )
            lines.append("")
        if targets.get("snapshot_stale"):
            age = targets.get("snapshot_age_days")
            label = "never run" if age is None else f"{age}d old"
            lines.append(f"Fit snapshot is {label} — run `beacon target fit --all` to keep the time series honest.")
            lines.append("")

    return "\n".join(lines) + "\n"
