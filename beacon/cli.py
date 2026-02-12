"""Beacon CLI — AI-First Company Intelligence Database.

Usage:
    beacon init              Initialize the database with seed data
    beacon companies         List all companies sorted by AI-first score
    beacon show <name>       Show detailed info for a company
    beacon scores refresh    Recompute all company scores
    beacon export markdown   Export company rankings as markdown
    beacon export csv        Export company data as CSV
    beacon stats             Show database statistics
    beacon scan              Scan career pages for job listings
    beacon jobs              List job listings sorted by relevance
    beacon job show <id>     Show detailed job info
    beacon job apply <id>    Mark a job as applied
    beacon job ignore <id>   Mark a job as ignored
    beacon report digest     Generate a job digest report
    beacon report jobs       Generate a full jobs report
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

try:
    import typer
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from beacon.db.connection import get_connection, init_db

app = typer.Typer(help="Beacon: AI-First Company Intelligence Database")
job_app = typer.Typer(help="Job listing operations")
report_app = typer.Typer(help="Report generation")
app.add_typer(job_app, name="job")
app.add_typer(report_app, name="report")
console = Console() if HAS_RICH else None


def _print(msg: str) -> None:
    if console:
        console.print(msg)
    else:
        print(msg)


@app.command()
def init(seed: bool = typer.Option(True, help="Seed with initial company data")):
    """Initialize the database and optionally seed with data."""
    init_db()
    _print("[green]✓[/green] Database initialized." if HAS_RICH else "✓ Database initialized.")

    if seed:
        from beacon.db.seed import seed_database
        conn = get_connection()
        counts = seed_database(conn)
        conn.close()
        _print(
            f"[green]✓[/green] Seeded: {counts['companies']} companies, "
            f"{counts['signals']} signals, {counts['leadership']} leadership signals, "
            f"{counts['tools']} tools"
            if HAS_RICH else
            f"✓ Seeded: {counts['companies']} companies, {counts['signals']} signals, "
            f"{counts['leadership']} leadership signals, {counts['tools']} tools"
        )


@app.command()
def companies(
    tier: int = typer.Option(None, "--tier", "-t", help="Filter by tier (1-4)"),
    min_score: float = typer.Option(None, "--min-score", "-m", help="Minimum AI-first score"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results"),
):
    """List companies sorted by AI-first score."""
    conn = get_connection()

    query = "SELECT * FROM companies WHERE 1=1"
    params = []

    if tier:
        query += " AND tier = ?"
        params.append(tier)
    if min_score:
        query += " AND ai_first_score >= ?"
        params.append(min_score)

    query += " ORDER BY ai_first_score DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        _print("No companies found matching criteria.")
        return

    if HAS_RICH:
        table = Table(title="AI-First Companies", show_lines=False)
        table.add_column("#", style="dim", width=3)
        table.add_column("Company", style="bold")
        table.add_column("Score", justify="right", style="green")
        table.add_column("Tier", justify="center")
        table.add_column("Remote", width=14)
        table.add_column("Industry")

        tier_labels = {1: "🟢 AI-Native", 2: "🔵 Convert", 3: "🟡 Strong", 4: "⚪ Emerging"}

        for i, r in enumerate(rows, 1):
            score_color = "green" if r["ai_first_score"] >= 7 else "yellow" if r["ai_first_score"] >= 4 else "red"
            table.add_row(
                str(i),
                r["name"],
                f"[{score_color}]{r['ai_first_score']:.1f}[/{score_color}]",
                tier_labels.get(r["tier"], "?"),
                r["remote_policy"] or "unknown",
                r["industry"] or "",
            )
        console.print(table)
    else:
        for i, r in enumerate(rows, 1):
            print(f"{i:3d}. [{r['ai_first_score']:.1f}] {r['name']} (Tier {r['tier']}, {r['remote_policy']})")


@app.command()
def show(name: str = typer.Argument(help="Company name (partial match)")):
    """Show detailed information for a company."""
    conn = get_connection()

    row = conn.execute(
        "SELECT * FROM companies WHERE name LIKE ?", (f"%{name}%",)
    ).fetchone()

    if not row:
        _print(f"No company found matching '{name}'")
        conn.close()
        return

    cid = row["id"]

    signals = conn.execute(
        "SELECT * FROM ai_signals WHERE company_id = ? ORDER BY signal_strength DESC", (cid,)
    ).fetchall()

    leadership = conn.execute(
        "SELECT * FROM leadership_signals WHERE company_id = ?", (cid,)
    ).fetchall()

    tools = conn.execute(
        "SELECT * FROM tools_adopted WHERE company_id = ?", (cid,)
    ).fetchall()

    scores = conn.execute(
        "SELECT * FROM score_breakdown WHERE company_id = ?", (cid,)
    ).fetchone()

    # Phase 2: show top active jobs
    active_jobs = conn.execute(
        "SELECT * FROM job_listings WHERE company_id = ? AND status = 'active' ORDER BY relevance_score DESC LIMIT 5",
        (cid,),
    ).fetchall()

    conn.close()

    if HAS_RICH:
        console.print(Panel(f"[bold]{row['name']}[/bold] — {row['description'] or ''}", style="blue"))
        console.print(f"  Score: [bold green]{row['ai_first_score']:.1f}[/bold green] / 10")
        console.print(f"  Tier: {row['tier']} | Remote: {row['remote_policy']} | Size: {row['size_bucket']}")
        console.print(f"  Industry: {row['industry']} | HQ: {row['hq_location']}")
        console.print(f"  Careers: {row['careers_url']}")

        if scores:
            console.print("\n[bold]Score Breakdown:[/bold]")
            console.print(f"  Leadership:      {scores['leadership_score']:.1f}")
            console.print(f"  Tool Adoption:   {scores['tool_adoption_score']:.1f}")
            console.print(f"  Culture:         {scores['culture_score']:.1f}")
            console.print(f"  Evidence Depth:  {scores['evidence_depth_score']:.1f}")
            console.print(f"  Recency:         {scores['recency_score']:.1f}")

        if leadership:
            console.print(f"\n[bold]Leadership Signals ({len(leadership)}):[/bold]")
            for s in leadership:
                console.print(f"  • {s['leader_name']} ({s['leader_title']}): {s['content'][:120]}...")

        if tools:
            console.print(f"\n[bold]Tools Adopted ({len(tools)}):[/bold]")
            for t in tools:
                console.print(f"  • {t['tool_name']} — {t['adoption_level']}")

        if signals:
            console.print(f"\n[bold]AI Signals ({len(signals)}):[/bold]")
            for s in signals:
                strength = "★" * (s["signal_strength"] or 0)
                console.print(f"  [{strength}] {s['title']}")

        if active_jobs:
            console.print(f"\n[bold]Top Active Jobs ({len(active_jobs)}):[/bold]")
            for j in active_jobs:
                score_color = "green" if j["relevance_score"] >= 7 else "yellow" if j["relevance_score"] >= 4 else "dim"
                loc = j['location'] or 'N/A'
                console.print(f"  [{score_color}]{j['relevance_score']:.1f}[/{score_color}] {j['title']} — {loc}")
    else:
        print(f"\n{row['name']} — Score: {row['ai_first_score']:.1f}/10, Tier: {row['tier']}")
        print(f"  {row['description']}")
        if active_jobs:
            print(f"\n  Top Active Jobs ({len(active_jobs)}):")
            for j in active_jobs:
                print(f"    [{j['relevance_score']:.1f}] {j['title']} — {j['location'] or 'N/A'}")


@app.command(name="scores")
def refresh_scores():
    """Recompute all company scores."""
    from beacon.research.scoring import refresh_all_scores
    conn = get_connection()
    count = refresh_all_scores(conn)
    conn.close()
    msg = f"[green]✓[/green] Refreshed scores for {count} companies"
    _print(msg if HAS_RICH else f"✓ Refreshed scores for {count} companies")


@app.command()
def stats():
    """Show database statistics."""
    conn = get_connection()
    companies_count = conn.execute("SELECT COUNT(*) as cnt FROM companies").fetchone()["cnt"]
    signals_count = conn.execute("SELECT COUNT(*) as cnt FROM ai_signals").fetchone()["cnt"]
    leadership_count = conn.execute("SELECT COUNT(*) as cnt FROM leadership_signals").fetchone()["cnt"]
    tools_count = conn.execute("SELECT COUNT(*) as cnt FROM tools_adopted").fetchone()["cnt"]

    tier_counts = conn.execute(
        "SELECT tier, COUNT(*) as cnt FROM companies GROUP BY tier ORDER BY tier"
    ).fetchall()

    avg_score = conn.execute("SELECT AVG(ai_first_score) as avg FROM companies").fetchone()["avg"]

    # Phase 2: job counts
    total_jobs = conn.execute("SELECT COUNT(*) as cnt FROM job_listings").fetchone()["cnt"]
    active_jobs = conn.execute("SELECT COUNT(*) as cnt FROM job_listings WHERE status = 'active'").fetchone()["cnt"]
    relevant_jobs = conn.execute(
        "SELECT COUNT(*) as cnt FROM job_listings WHERE status = 'active' AND relevance_score >= 7"
    ).fetchone()["cnt"]

    conn.close()

    _print("\n[bold]Beacon Database Stats[/bold]" if HAS_RICH else "\nBeacon Database Stats")
    _print(f"  Companies:         {companies_count}")
    _print(f"  AI Signals:        {signals_count}")
    _print(f"  Leadership Signals: {leadership_count}")
    _print(f"  Tools Tracked:     {tools_count}")
    _print(f"  Average Score:     {avg_score:.1f}" if avg_score else "  Average Score:     N/A")

    for tc in tier_counts:
        tier_labels = {1: "AI-Native", 2: "AI-First Convert", 3: "Strong Adoption", 4: "Emerging"}
        _print(f"  Tier {tc['tier']} ({tier_labels.get(tc['tier'], '?')}): {tc['cnt']}")

    if total_jobs > 0:
        _print(
            f"\n  Job Listings:      {total_jobs} total, {active_jobs} active, "
            f"{relevant_jobs} relevant (score >= 7)"
        )


@app.command()
def export(
    format: str = typer.Argument(help="Export format: markdown, csv, json, report"),
    min_score: float = typer.Option(None, "--min-score", "-m"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Export company data in various formats."""
    from beacon.export.formatters import (
        export_csv,
        export_json,
        export_markdown_table,
        export_report,
    )

    conn = get_connection()

    if format == "markdown":
        content = export_markdown_table(conn, min_score)
    elif format == "csv":
        content = export_csv(conn, min_score)
    elif format == "json":
        content = export_json(conn, min_score)
    elif format == "report":
        content = export_report(conn)
    else:
        _print(f"Unknown format: {format}. Use markdown, csv, json, or report.")
        conn.close()
        return

    conn.close()

    if output:
        Path(output).write_text(content)
        _print(f"Exported to {output}")
    else:
        print(content)


# --- Phase 2: Job Scanner commands ---

@app.command()
def scan(
    company: str = typer.Option(None, "--company", "-c", help="Company name filter"),
    platform: str = typer.Option(None, "--platform", "-p", help="Platform filter (greenhouse, lever, ashby, custom)"),
    min_score: float = typer.Option(None, "--min-score", "-m", help="Minimum company AI-first score"),
):
    """Scan career pages for job listings."""
    try:
        import httpx  # noqa: F401
    except ImportError:
        _print("Scraping dependencies not installed. Run: pip install beacon[scraping]")
        raise typer.Exit(1)

    from beacon.scanner import scan_all

    conn = get_connection()
    _print("Scanning career pages..." if not HAS_RICH else "[bold]Scanning career pages...[/bold]")

    results = scan_all(conn, platform=platform, company_name=company, min_score=min_score)
    conn.close()

    if not results:
        _print("No companies matched the filter criteria.")
        return

    if HAS_RICH:
        table = Table(title="Scan Results")
        table.add_column("Company", style="bold")
        table.add_column("Platform")
        table.add_column("Found", justify="right")
        table.add_column("New", justify="right", style="green")
        table.add_column("Updated", justify="right")
        table.add_column("Stale", justify="right", style="yellow")
        table.add_column("Status")

        for r in results:
            status = "[red]Error[/red]" if r.error else "[green]OK[/green]"
            table.add_row(
                r.company_name,
                r.platform,
                str(r.jobs_found),
                str(r.new_jobs),
                str(r.updated_jobs),
                str(r.stale_jobs),
                status if HAS_RICH else ("Error" if r.error else "OK"),
            )
        console.print(table)
    else:
        for r in results:
            status = f"ERROR: {r.error}" if r.error else "OK"
            print(f"  {r.company_name} ({r.platform}): {r.jobs_found} found, "
                  f"{r.new_jobs} new, {r.stale_jobs} stale — {status}")

    total_new = sum(r.new_jobs for r in results)
    total_found = sum(r.jobs_found for r in results)
    errors = sum(1 for r in results if r.error)
    _print(f"\nTotal: {total_found} jobs found, {total_new} new, {errors} errors")


@app.command()
def jobs(
    company: str = typer.Option(None, "--company", "-c", help="Company name filter"),
    status: str = typer.Option(None, "--status", "-s", help="Filter by status (active, closed, applied, ignored)"),
    min_relevance: float = typer.Option(None, "--min-relevance", "-r", help="Minimum relevance score"),
    new: bool = typer.Option(False, "--new", help="Show only jobs from last 24 hours"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results"),
):
    """List job listings sorted by relevance score."""
    from beacon.db.jobs import get_jobs, get_new_jobs_since

    conn = get_connection()

    if new:
        since = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        rows = get_new_jobs_since(conn, since, min_relevance)
    else:
        company_id = None
        if company:
            c = conn.execute("SELECT id FROM companies WHERE name LIKE ?", (f"%{company}%",)).fetchone()
            if c:
                company_id = c["id"]
            else:
                _print(f"No company found matching '{company}'")
                conn.close()
                return
        rows = get_jobs(conn, company_id=company_id, status=status, min_relevance=min_relevance, limit=limit)

    conn.close()

    if not rows:
        _print("No jobs found matching criteria.")
        return

    if HAS_RICH:
        table = Table(title="Job Listings")
        table.add_column("ID", style="dim", width=5)
        table.add_column("Company", style="bold")
        table.add_column("Title")
        table.add_column("Relevance", justify="right")
        table.add_column("Location", width=20)
        table.add_column("Status")

        for r in rows:
            score_color = "green" if r["relevance_score"] >= 7 else "yellow" if r["relevance_score"] >= 4 else "dim"
            table.add_row(
                str(r["id"]),
                r["company_name"],
                r["title"][:50],
                f"[{score_color}]{r['relevance_score']:.1f}[/{score_color}]",
                (r["location"] or "")[:20],
                r["status"],
            )
        console.print(table)
    else:
        for r in rows:
            print(f"  [{r['id']}] [{r['relevance_score']:.1f}] {r['company_name']}: {r['title']} ({r['status']})")


@job_app.command("show")
def job_show(job_id: int = typer.Argument(help="Job listing ID")):
    """Show detailed information for a job listing."""
    from beacon.db.jobs import get_job_by_id

    conn = get_connection()
    job = get_job_by_id(conn, job_id)
    conn.close()

    if not job:
        _print(f"No job found with ID {job_id}")
        return

    if HAS_RICH:
        console.print(Panel(f"[bold]{job['title']}[/bold] at {job['company_name']}", style="blue"))
        console.print(f"  Relevance: [bold]{job['relevance_score']:.1f}[/bold] / 10")
        console.print(f"  Location: {job['location'] or 'N/A'}")
        console.print(f"  Department: {job['department'] or 'N/A'}")
        console.print(f"  Status: {job['status']}")
        console.print(f"  Posted: {job['date_posted'] or 'N/A'}")
        console.print(f"  First seen: {job['date_first_seen']}")
        console.print(f"  Last seen: {job['date_last_seen']}")
        if job["url"]:
            console.print(f"  URL: {job['url']}")
        if job["match_reasons"]:
            reasons = json.loads(job["match_reasons"])
            console.print("\n[bold]Match Reasons:[/bold]")
            for r in reasons:
                console.print(f"  • {r}")
        if job["description_text"]:
            console.print("\n[bold]Description:[/bold]")
            console.print(f"  {job['description_text'][:500]}")
    else:
        print(f"\n{job['title']} at {job['company_name']}")
        print(f"  Relevance: {job['relevance_score']:.1f}/10 | Status: {job['status']}")
        print(f"  Location: {job['location'] or 'N/A'} | Department: {job['department'] or 'N/A'}")
        if job["url"]:
            print(f"  URL: {job['url']}")


@job_app.command("apply")
def job_apply(job_id: int = typer.Argument(help="Job listing ID")):
    """Mark a job as applied."""
    from beacon.db.jobs import update_job_status

    conn = get_connection()
    success = update_job_status(conn, job_id, "applied")
    conn.close()

    if success:
        _print(f"[green]✓[/green] Job {job_id} marked as applied" if HAS_RICH else f"✓ Job {job_id} marked as applied")
    else:
        _print(f"No job found with ID {job_id}")


@job_app.command("ignore")
def job_ignore(job_id: int = typer.Argument(help="Job listing ID")):
    """Mark a job as ignored."""
    from beacon.db.jobs import update_job_status

    conn = get_connection()
    success = update_job_status(conn, job_id, "ignored")
    conn.close()

    if success:
        _print(f"[green]✓[/green] Job {job_id} marked as ignored" if HAS_RICH else f"✓ Job {job_id} marked as ignored")
    else:
        _print(f"No job found with ID {job_id}")


# --- Phase 2: Report commands ---

@report_app.command("digest")
def report_digest(
    since: str = typer.Option(None, "--since", help="Date (YYYY-MM-DD) to filter jobs from"),
    min_relevance: float = typer.Option(7.0, "--min-relevance", "-r"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Generate a markdown digest of recent relevant jobs."""
    from beacon.export.formatters import export_jobs_digest

    if not since:
        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    conn = get_connection()
    content = export_jobs_digest(conn, since, min_relevance)
    conn.close()

    if output:
        Path(output).write_text(content)
        _print(f"Digest written to {output}")
    else:
        print(content)


@report_app.command("jobs")
def report_jobs(
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Generate a full markdown report of all job listings."""
    from beacon.export.formatters import export_jobs_report

    conn = get_connection()
    content = export_jobs_report(conn)
    conn.close()

    if output:
        Path(output).write_text(content)
        _print(f"Report written to {output}")
    else:
        print(content)


def main():
    app()


if __name__ == "__main__":
    main()
