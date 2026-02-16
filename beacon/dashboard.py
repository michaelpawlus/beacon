"""Dashboard data gathering for Beacon Phase 5."""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class DashboardData:
    """All data needed to render the dashboard."""

    # Header stats
    company_count: int = 0
    active_job_count: int = 0
    application_count: int = 0
    profile_completeness: int = 0

    # Watchlist: top companies by score
    watchlist: list[dict] = field(default_factory=list)

    # Top job matches
    top_jobs: list[dict] = field(default_factory=list)

    # Application pipeline counts
    pipeline: dict[str, int] = field(default_factory=dict)

    # Presence health indicators
    presence: dict[str, dict] = field(default_factory=dict)

    # Content pipeline
    content: dict[str, int] = field(default_factory=dict)

    # Feedback summary
    feedback: dict[str, int] = field(default_factory=dict)

    # Action items
    action_items: list[str] = field(default_factory=list)

    # Date
    date: str = ""


def _compute_profile_completeness(conn: sqlite3.Connection) -> int:
    """Compute profile completeness percentage."""
    sections = [
        ("work_experiences", 1),
        ("projects", 2),
        ("skills", 5),
        ("education", 1),
        ("publications_talks", 0),
    ]
    filled = 0
    for table, minimum in sections:
        count = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()["cnt"]
        if count >= minimum:
            filled += 1
    return int((filled / len(sections)) * 100)


def _get_watchlist(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """Get top companies by score with job counts."""
    rows = conn.execute(
        """SELECT c.id, c.name, c.ai_first_score, c.tier,
                  COUNT(CASE WHEN j.status = 'active' THEN 1 END) as active_jobs
           FROM companies c
           LEFT JOIN job_listings j ON c.id = j.company_id
           GROUP BY c.id
           ORDER BY c.ai_first_score DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def _get_top_jobs(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """Get highest-relevance active jobs."""
    rows = conn.execute(
        """SELECT j.id, j.title, j.relevance_score, j.status, c.name as company_name
           FROM job_listings j
           JOIN companies c ON j.company_id = c.id
           WHERE j.status = 'active' AND j.relevance_score > 0
           ORDER BY j.relevance_score DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def _get_pipeline(conn: sqlite3.Connection) -> dict[str, int]:
    """Get application pipeline counts by status."""
    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
    ).fetchall()
    return {r["status"]: r["cnt"] for r in rows}


def _get_presence_health(conn: sqlite3.Connection) -> dict[str, dict]:
    """Compute presence health indicators."""
    completeness = _compute_profile_completeness(conn)
    completeness_status = "green" if completeness >= 80 else "yellow" if completeness >= 50 else "red"

    # Last content created
    last_draft = conn.execute(
        "SELECT created_at FROM content_drafts ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if last_draft:
        created = datetime.fromisoformat(last_draft["created_at"])
        days_ago = (datetime.now() - created).days
        content_status = "green" if days_ago <= 7 else "yellow" if days_ago <= 14 else "red"
        content_label = f"{days_ago}d ago"
    else:
        content_status = "red"
        content_label = "never"

    # Calendar status
    now = datetime.now().strftime("%Y-%m-%d")
    overdue = conn.execute(
        "SELECT COUNT(*) as cnt FROM content_calendar WHERE target_date < ? AND status != 'published'",
        (now,),
    ).fetchone()["cnt"]
    calendar_status = "green" if overdue == 0 else "yellow" if overdue <= 2 else "red"
    calendar_label = "on track" if overdue == 0 else f"{overdue} overdue"

    return {
        "profile_completeness": {"value": f"{completeness}%", "status": completeness_status},
        "last_content": {"value": content_label, "status": content_status},
        "content_calendar": {"value": calendar_label, "status": calendar_status},
    }


def _get_content_pipeline(conn: sqlite3.Connection) -> dict[str, int]:
    """Get content pipeline stats."""
    drafts = conn.execute(
        "SELECT COUNT(*) as cnt FROM content_drafts WHERE status = 'draft'"
    ).fetchone()["cnt"]

    now = datetime.now()
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    week_end = (now + timedelta(days=6 - now.weekday())).strftime("%Y-%m-%d")
    this_week = conn.execute(
        "SELECT COUNT(*) as cnt FROM content_calendar WHERE target_date BETWEEN ? AND ?",
        (week_start, week_end),
    ).fetchone()["cnt"]

    today = now.strftime("%Y-%m-%d")
    overdue = conn.execute(
        "SELECT COUNT(*) as cnt FROM content_calendar WHERE target_date < ? AND status != 'published'",
        (today,),
    ).fetchone()["cnt"]

    return {"drafts_ready": drafts, "this_week": this_week, "overdue": overdue}


def _get_feedback_summary(conn: sqlite3.Connection) -> dict[str, int]:
    """Get feedback summary counts."""
    total = conn.execute("SELECT COUNT(*) as cnt FROM application_outcomes").fetchone()["cnt"]
    positive = conn.execute(
        """SELECT COUNT(*) as cnt FROM application_outcomes
           WHERE outcome IN ('phone_screen', 'technical', 'onsite', 'offer', 'accepted')"""
    ).fetchone()["cnt"]
    return {"total_outcomes": total, "positive_outcomes": positive}


def _generate_action_items(conn: sqlite3.Connection) -> list[str]:
    """Generate prioritized action items."""
    items = []

    # New high-relevance jobs
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    new_relevant = conn.execute(
        """SELECT COUNT(*) as cnt FROM job_listings
           WHERE date_first_seen >= ? AND relevance_score >= 8.0 AND status = 'active'""",
        (yesterday,),
    ).fetchone()["cnt"]
    if new_relevant:
        items.append(f"{new_relevant} new high-relevance jobs since last check (score >= 8.0)")

    # Applications needing outcome tracking
    stale_apps = conn.execute(
        """SELECT a.id, julianday('now') - julianday(a.applied_date) as days_since
           FROM applications a
           LEFT JOIN application_outcomes ao ON a.id = ao.application_id
           WHERE a.status = 'applied' AND ao.id IS NULL AND a.applied_date IS NOT NULL
           AND julianday('now') - julianday(a.applied_date) > 7
           ORDER BY days_since DESC LIMIT 3"""
    ).fetchall()
    for app in stale_apps:
        items.append(f"Record outcome for application #{app['id']} (applied {int(app['days_since'])} days ago)")

    # Stale company signals
    stale_signals = conn.execute(
        """SELECT c.name, julianday('now') - julianday(c.last_researched_at) as days_stale
           FROM companies c
           WHERE c.last_researched_at IS NOT NULL
           AND julianday('now') - julianday(c.last_researched_at) > 30
           ORDER BY days_stale DESC LIMIT 3"""
    ).fetchall()
    if stale_signals:
        names = ", ".join(f"{s['name']} ({int(s['days_stale'])}d)" for s in stale_signals)
        items.append(f"Signals stale for: {names}")

    # Overdue calendar items
    today = datetime.now().strftime("%Y-%m-%d")
    overdue = conn.execute(
        "SELECT COUNT(*) as cnt FROM content_calendar WHERE target_date < ? AND status != 'published'",
        (today,),
    ).fetchone()["cnt"]
    if overdue:
        items.append(f"{overdue} overdue content calendar items")

    # Draft content ready to publish
    drafts = conn.execute(
        "SELECT COUNT(*) as cnt FROM content_drafts WHERE status = 'draft'"
    ).fetchone()["cnt"]
    if drafts >= 3:
        items.append(f"{drafts} content drafts ready to publish")

    return items


def gather_dashboard_data(conn: sqlite3.Connection) -> DashboardData:
    """Gather all data needed for the dashboard."""
    data = DashboardData()
    data.date = datetime.now().strftime("%b %d, %Y")

    # Header stats
    data.company_count = conn.execute("SELECT COUNT(*) as cnt FROM companies").fetchone()["cnt"]
    data.active_job_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM job_listings WHERE status = 'active'"
    ).fetchone()["cnt"]
    data.application_count = conn.execute("SELECT COUNT(*) as cnt FROM applications").fetchone()["cnt"]
    data.profile_completeness = _compute_profile_completeness(conn)

    # Sections
    data.watchlist = _get_watchlist(conn)
    data.top_jobs = _get_top_jobs(conn)
    data.pipeline = _get_pipeline(conn)
    data.presence = _get_presence_health(conn)
    data.content = _get_content_pipeline(conn)
    data.feedback = _get_feedback_summary(conn)
    data.action_items = _generate_action_items(conn)

    return data
