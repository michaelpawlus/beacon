"""Notification message formatters for Beacon."""


def format_new_jobs_alert(jobs: list[dict]) -> str:
    """Format a notification about new high-relevance jobs."""
    if not jobs:
        return "No new relevant jobs found."

    lines = [f"Found {len(jobs)} new relevant job(s):\n"]
    for j in jobs:
        company = j.get("company_name", "Unknown")
        title = j.get("title", "Unknown")
        score = j.get("relevance_score", 0)
        lines.append(f"  [{score:.1f}] {company}: {title}")

    lines.append("\nRun 'beacon jobs --new' to see details.")
    return "\n".join(lines)


def format_digest(dashboard_data) -> str:
    """Format a daily digest from dashboard data."""
    lines = [f"Beacon Daily Digest — {dashboard_data.date}\n"]

    lines.append(
        f"Companies: {dashboard_data.company_count} | "
        f"Active Jobs: {dashboard_data.active_job_count} | "
        f"Applications: {dashboard_data.application_count}"
    )

    if dashboard_data.top_jobs:
        lines.append("\nTop Matches:")
        for j in dashboard_data.top_jobs[:5]:
            lines.append(f"  [{j['relevance_score']:.1f}] {j['company_name']}: {j['title']}")

    if dashboard_data.pipeline:
        lines.append("\nPipeline:")
        for stage, count in dashboard_data.pipeline.items():
            lines.append(f"  {stage}: {count}")

    if dashboard_data.action_items:
        lines.append("\nAction Items:")
        for i, item in enumerate(dashboard_data.action_items):
            lines.append(f"  {i+1}. {item}")

    lines.append("\nRun 'beacon dashboard' for the full view.")
    return "\n".join(lines)


def format_action_items(items: list[str]) -> str:
    """Format action items for notification."""
    if not items:
        return "No pending action items."

    lines = ["Beacon Action Items:\n"]
    for i, item in enumerate(items):
        lines.append(f"  {i+1}. {item}")
    return "\n".join(lines)
