"""Dashboard rendering for Beacon Phase 5 using Rich."""

from beacon.dashboard import DashboardData

# Status indicator mapping
_STATUS_ICONS = {"green": "[G]", "yellow": "[Y]", "red": "[R]"}


def render_dashboard(console, data: DashboardData, compact: bool = False) -> None:
    """Render the dashboard. Uses Rich console if available, else plain text."""
    if console is not None:
        _render_rich(console, data, compact)
    else:
        _render_plain(data, compact)


def _render_rich(console, data: DashboardData, compact: bool) -> None:
    """Render dashboard with Rich panels and tables."""
    from rich.panel import Panel
    from rich.table import Table

    # Header
    header = (
        f"  {data.company_count} companies | {data.active_job_count} active jobs | "
        f"{data.application_count} applications | Profile: {data.profile_completeness}%"
    )
    console.print(Panel(header, title=f"Beacon Dashboard — {data.date}", style="bold blue"))

    if compact:
        _render_compact_rich(console, data)
        return

    # Watchlist
    if data.watchlist:
        wt = Table(title="Company Watchlist", show_lines=False)
        wt.add_column("Company", style="bold", width=20)
        wt.add_column("Score", justify="right", style="green", width=6)
        wt.add_column("Tier", justify="center", width=6)
        wt.add_column("Jobs", justify="right", width=5)
        tier_labels = {1: "AI-N", 2: "Conv", 3: "Strg", 4: "Emrg"}
        for c in data.watchlist[:8]:
            score = c["ai_first_score"] or 0
            score_color = "green" if score >= 7 else "yellow" if score >= 4 else "dim"
            wt.add_row(
                c["name"][:20],
                f"[{score_color}]{score:.1f}[/{score_color}]",
                tier_labels.get(c["tier"], "?"),
                str(c["active_jobs"]),
            )
        console.print(wt)

    # Top jobs
    if data.top_jobs:
        jt = Table(title="Top Job Matches", show_lines=False)
        jt.add_column("Rel", justify="right", width=5)
        jt.add_column("Company", style="bold", width=15)
        jt.add_column("Title", width=30)
        jt.add_column("Status", width=8)
        for j in data.top_jobs[:8]:
            score_color = "green" if j["relevance_score"] >= 7 else "yellow" if j["relevance_score"] >= 4 else "dim"
            jt.add_row(
                f"[{score_color}]{j['relevance_score']:.1f}[/{score_color}]",
                j["company_name"][:15],
                j["title"][:30],
                j["status"],
            )
        console.print(jt)

    # Application pipeline
    if data.pipeline:
        stages = ["draft", "applied", "phone_screen", "interview", "offer"]
        parts = []
        for stage in stages:
            count = data.pipeline.get(stage, 0)
            label = stage.replace("_", " ").title()
            parts.append(f"{label}: {count}")
        pipeline_text = " → ".join(parts)
        console.print(Panel(pipeline_text, title="Application Pipeline"))

    # Presence health
    if data.presence:
        from rich.table import Table
        pt = Table(title="Presence Health", show_lines=False)
        pt.add_column("Metric", width=25)
        pt.add_column("Value", width=15)
        pt.add_column("", width=3)
        for key, info in data.presence.items():
            label = key.replace("_", " ").title()
            status_color = info["status"]
            icon = f"[{status_color}]{_STATUS_ICONS[status_color]}[/{status_color}]"
            pt.add_row(label, info["value"], icon)
        console.print(pt)

    # Content pipeline
    if data.content:
        console.print(Panel(
            f"  Drafts ready to publish: {data.content.get('drafts_ready', 0)}\n"
            f"  Calendar items this week: {data.content.get('this_week', 0)}\n"
            f"  Overdue items: {data.content.get('overdue', 0)}",
            title="Content Pipeline",
        ))

    # Action items
    if data.action_items:
        items_text = "\n".join(f"  {i+1}. {item}" for i, item in enumerate(data.action_items))
        console.print(Panel(items_text, title="Action Items", style="yellow"))
    else:
        console.print(Panel("  No action items — you're all caught up!", title="Action Items", style="green"))


def _render_compact_rich(console, data: DashboardData) -> None:
    """Render compact dashboard (fewer sections)."""
    # Just top jobs and action items
    if data.top_jobs:
        for j in data.top_jobs[:5]:
            console.print(f"  [{j['relevance_score']:.1f}] {j['company_name']}: {j['title']}")

    if data.action_items:
        console.print("\n[bold]Action Items:[/bold]")
        for i, item in enumerate(data.action_items[:3]):
            console.print(f"  {i+1}. {item}")


def _render_plain(data: DashboardData, compact: bool) -> None:
    """Render dashboard in plain text."""
    print(f"\n=== Beacon Dashboard — {data.date} ===")
    print(
        f"  {data.company_count} companies | {data.active_job_count} active jobs | "
        f"{data.application_count} applications | Profile: {data.profile_completeness}%"
    )

    if compact:
        if data.top_jobs:
            print("\nTop Jobs:")
            for j in data.top_jobs[:5]:
                print(f"  [{j['relevance_score']:.1f}] {j['company_name']}: {j['title']}")
        if data.action_items:
            print("\nAction Items:")
            for i, item in enumerate(data.action_items[:3]):
                print(f"  {i+1}. {item}")
        return

    if data.watchlist:
        print("\nCompany Watchlist:")
        for c in data.watchlist[:8]:
            score = c["ai_first_score"] or 0
            print(f"  [{score:.1f}] {c['name']} (Tier {c['tier']}, {c['active_jobs']} jobs)")

    if data.top_jobs:
        print("\nTop Job Matches:")
        for j in data.top_jobs[:8]:
            print(f"  [{j['relevance_score']:.1f}] {j['company_name']}: {j['title']}")

    if data.pipeline:
        print("\nApplication Pipeline:")
        parts = [f"{k}: {v}" for k, v in data.pipeline.items()]
        print(f"  {' → '.join(parts)}")

    if data.presence:
        print("\nPresence Health:")
        for key, info in data.presence.items():
            label = key.replace("_", " ").title()
            print(f"  {label}: {info['value']} {_STATUS_ICONS[info['status']]}")

    if data.action_items:
        print("\nAction Items:")
        for i, item in enumerate(data.action_items):
            print(f"  {i+1}. {item}")
    else:
        print("\nNo action items — you're all caught up!")
