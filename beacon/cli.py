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
import sys
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
profile_app = typer.Typer(help="Professional profile management")
application_app = typer.Typer(help="Application tracking")
presence_app = typer.Typer(help="Professional presence & content generation")
config_app = typer.Typer(help="Configuration management")
automation_app = typer.Typer(help="Automation and scheduling")
session_app = typer.Typer(help="Claude Code session logging")
media_app = typer.Typer(help="Media log — track videos, podcasts, articles")
network_app = typer.Typer(help="Networking — events and professional contacts")
app.add_typer(job_app, name="job")
app.add_typer(report_app, name="report")
app.add_typer(profile_app, name="profile")
app.add_typer(application_app, name="application")
app.add_typer(presence_app, name="presence")
app.add_typer(config_app, name="config")
app.add_typer(automation_app, name="automation")
app.add_typer(session_app, name="session")
app.add_typer(media_app, name="media")
app.add_typer(network_app, name="network")
console = Console() if HAS_RICH else None


def _print(msg: str) -> None:
    if console:
        console.print(msg)
    else:
        print(msg)


def _stderr(msg: str) -> None:
    """Print human-readable message to stderr (used in --json mode)."""
    print(msg, file=sys.stderr)


def _json_out(data) -> None:
    """Write JSON to stdout and return."""
    print(json.dumps(data, default=str))


def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row) if row else {}


def _rows_to_list(rows) -> list[dict]:
    """Convert a list of sqlite3.Row to list of dicts."""
    return [dict(r) for r in rows]


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
    tools: str = typer.Option(None, "--tools", help="Filter by adopted tool name (partial match)"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List companies sorted by AI-first score."""
    conn = get_connection()

    if tools:
        query = (
            "SELECT DISTINCT c.* FROM companies c"
            " JOIN tools_adopted t ON c.id = t.company_id"
            " WHERE t.tool_name LIKE ?"
        )
        params: list = [f"%{tools}%"]
        col_prefix = "c."
    else:
        query = "SELECT * FROM companies WHERE 1=1"
        params = []
        col_prefix = ""

    if tier:
        query += f" AND {col_prefix}tier = ?"
        params.append(tier)
    if min_score:
        query += f" AND {col_prefix}ai_first_score >= ?"
        params.append(min_score)

    query += f" ORDER BY {col_prefix}ai_first_score DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if as_json:
        _json_out(_rows_to_list(rows))
        return

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
def show(
    name: str = typer.Argument(help="Company name (partial match)"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show detailed information for a company."""
    conn = get_connection()

    row = conn.execute(
        "SELECT * FROM companies WHERE name LIKE ?", (f"%{name}%",)
    ).fetchone()

    if not row:
        if as_json:
            _json_out({"error": f"No company found matching '{name}'", "code": 2})
        else:
            _print(f"No company found matching '{name}'")
        conn.close()
        raise typer.Exit(2)

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

    if as_json:
        data = _row_to_dict(row)
        data["signals"] = _rows_to_list(signals)
        data["leadership"] = _rows_to_list(leadership)
        data["tools"] = _rows_to_list(tools)
        data["score_breakdown"] = _row_to_dict(scores) if scores else None
        data["active_jobs"] = _rows_to_list(active_jobs)
        _json_out(data)
        return

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
def stats(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
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

    if as_json:
        _json_out({
            "companies": companies_count,
            "ai_signals": signals_count,
            "leadership_signals": leadership_count,
            "tools": tools_count,
            "average_score": round(avg_score, 1) if avg_score else None,
            "tiers": {str(tc["tier"]): tc["cnt"] for tc in tier_counts},
            "jobs_total": total_jobs,
            "jobs_active": active_jobs,
            "jobs_relevant": relevant_jobs,
        })
        return

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
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Scan career pages for job listings."""
    try:
        import httpx  # noqa: F401
    except ImportError:
        if as_json:
            _json_out({"error": "Scraping dependencies not installed. Run: pip install beacon[scraping]", "code": 1})
        else:
            _print("Scraping dependencies not installed. Run: pip install beacon[scraping]")
        raise typer.Exit(1)

    from beacon.scanner import scan_all

    conn = get_connection()
    if not as_json:
        _print("Scanning career pages..." if not HAS_RICH else "[bold]Scanning career pages...[/bold]")

    results = scan_all(conn, platform=platform, company_name=company, min_score=min_score)
    conn.close()

    if as_json:
        data = [
            {
                "company": r.company_name, "platform": r.platform,
                "jobs_found": r.jobs_found, "new_jobs": r.new_jobs,
                "updated_jobs": r.updated_jobs, "stale_jobs": r.stale_jobs,
                "error": r.error,
            }
            for r in results
        ]
        _json_out(data)
        return

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
    since: str = typer.Option(None, "--since", help="Show jobs first seen after date (YYYY-MM-DD)"),
    new: bool = typer.Option(False, "--new", help="Show only jobs from last 24 hours"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List job listings sorted by relevance score."""
    from beacon.db.jobs import get_jobs, get_new_jobs_since

    conn = get_connection()

    if new or since:
        since_dt = since or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        rows = get_new_jobs_since(conn, since_dt, min_relevance)
    else:
        company_id = None
        if company:
            c = conn.execute("SELECT id FROM companies WHERE name LIKE ?", (f"%{company}%",)).fetchone()
            if c:
                company_id = c["id"]
            else:
                if as_json:
                    _json_out({"error": f"No company found matching '{company}'", "code": 2})
                else:
                    _print(f"No company found matching '{company}'")
                conn.close()
                raise typer.Exit(2)
        rows = get_jobs(conn, company_id=company_id, status=status, min_relevance=min_relevance, limit=limit)

    conn.close()

    if as_json:
        _json_out(_rows_to_list(rows))
        return

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
def job_show(
    job_id: int = typer.Argument(help="Job listing ID"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show detailed information for a job listing."""
    from beacon.db.jobs import get_job_by_id

    conn = get_connection()
    job = get_job_by_id(conn, job_id)
    conn.close()

    if not job:
        if as_json:
            _json_out({"error": f"No job found with ID {job_id}", "code": 2})
        else:
            _print(f"No job found with ID {job_id}")
        raise typer.Exit(2)

    if as_json:
        data = _row_to_dict(job)
        if data.get("match_reasons"):
            try:
                data["match_reasons"] = json.loads(data["match_reasons"])
            except (json.JSONDecodeError, TypeError):
                pass
        _json_out(data)
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
def job_apply(
    job_id: int = typer.Argument(help="Job listing ID"),
    generate_materials: bool = typer.Option(False, "--generate", "-g", help="Generate resume and cover letter"),
    notes: str = typer.Option(None, "--notes", "-n", help="Application notes"),
):
    """Mark a job as applied and optionally create an application record."""
    from beacon.db.jobs import update_job_status
    from beacon.db.profile import add_application

    conn = get_connection()
    success = update_job_status(conn, job_id, "applied")

    if not success:
        _print(f"No job found with ID {job_id}")
        conn.close()
        return

    # Create application record
    from datetime import datetime as dt
    app_id = add_application(conn, job_id, status="applied",
                              applied_date=dt.now().strftime("%Y-%m-%d"),
                              notes=notes)
    _print(f"[green]✓[/green] Job {job_id} marked as applied (application #{app_id})" if HAS_RICH else f"✓ Job {job_id} marked as applied (application #{app_id})")

    if generate_materials:
        _print("Generating application materials..." if not HAS_RICH else "[bold]Generating application materials...[/bold]")
        try:
            from beacon.materials.renderer import render_markdown
            from beacon.materials.resume import tailor_resume
            result = tailor_resume(conn, job_id)
            resume_path = f"resume_{job_id}.md"
            Path(resume_path).write_text(render_markdown(result))
            from beacon.db.profile import update_application
            update_application(conn, app_id, resume_path=resume_path)
            _print(f"  [green]✓[/green] Resume saved to {resume_path}" if HAS_RICH else f"  ✓ Resume saved to {resume_path}")
        except RuntimeError as e:
            _print(f"  [yellow]⚠[/yellow] Resume generation skipped: {e}" if HAS_RICH else f"  ⚠ Resume generation skipped: {e}")
        try:
            from beacon.materials.cover_letter import generate_cover_letter
            content = generate_cover_letter(conn, job_id)
            cl_path = f"cover_letter_{job_id}.md"
            Path(cl_path).write_text(content)
            from beacon.db.profile import update_application
            update_application(conn, app_id, cover_letter_path=cl_path)
            _print(f"  [green]✓[/green] Cover letter saved to {cl_path}" if HAS_RICH else f"  ✓ Cover letter saved to {cl_path}")
        except RuntimeError as e:
            _print(f"  [yellow]⚠[/yellow] Cover letter generation skipped: {e}" if HAS_RICH else f"  ⚠ Cover letter generation skipped: {e}")

    conn.close()


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
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Generate a markdown digest of recent relevant jobs."""
    from beacon.export.formatters import export_jobs_digest

    if not since:
        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    conn = get_connection()
    content = export_jobs_digest(conn, since, min_relevance)
    conn.close()

    if as_json:
        _json_out({"since": since, "min_relevance": min_relevance, "content": content})
        return

    if output:
        Path(output).write_text(content)
        _print(f"Digest written to {output}")
    else:
        print(content)


@report_app.command("jobs")
def report_jobs(
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Generate a full markdown report of all job listings."""
    from beacon.export.formatters import export_jobs_report

    conn = get_connection()
    content = export_jobs_report(conn)
    conn.close()

    if as_json:
        _json_out({"content": content})
        return

    if output:
        Path(output).write_text(content)
        _print(f"Report written to {output}")
    else:
        print(content)


# --- Phase 3: Profile commands ---

@profile_app.command("interview")
def profile_interview(
    section: str = typer.Option(None, "--section", "-s", help="Interview section: work, projects, skills, education, publications"),
    data: str = typer.Option(None, "--data", "-d", help="JSON string with profile data (skips interactive prompts)"),
):
    """Interactive interview to build your professional profile."""
    from beacon.interview import SECTION_LABELS, run_full_interview

    # Non-interactive path: --data flag with JSON string
    if data is not None:
        from beacon.importer import import_profile_from_dict

        conn = get_connection()
        try:
            profile_data = json.loads(data)
        except json.JSONDecodeError as e:
            _print(f"Invalid JSON: {e}")
            conn.close()
            raise typer.Exit(1)

        counts = import_profile_from_dict(conn, profile_data)
        errors = counts.pop("errors", [])
        for key, count in counts.items():
            _print(f"  {key}: {count} entries imported")
        if errors:
            _print(f"  Errors: {len(errors)}")
            for err in errors:
                _print(f"    - {err}")
        conn.close()
        return

    # Non-interactive path: piped JSON via stdin
    if not sys.stdin.isatty():
        stdin_data = sys.stdin.read().strip()
        if not stdin_data:
            _print("Error: profile interview requires an interactive terminal or JSON input.")
            _print("  Interactive:  beacon profile interview [--section education]")
            _print("  JSON flag:    beacon profile interview --data '{\"education\": [...]}'")
            _print("  Piped JSON:   echo '{...}' | beacon profile interview")
            _print("  File import:  beacon profile import profile.json")
            raise typer.Exit(1)

        from beacon.importer import import_profile_from_dict

        conn = get_connection()
        try:
            profile_data = json.loads(stdin_data)
        except json.JSONDecodeError as e:
            _print(f"Invalid JSON from stdin: {e}")
            conn.close()
            raise typer.Exit(1)

        counts = import_profile_from_dict(conn, profile_data)
        errors = counts.pop("errors", [])
        for key, count in counts.items():
            _print(f"  {key}: {count} entries imported")
        if errors:
            _print(f"  Errors: {len(errors)}")
            for err in errors:
                _print(f"    - {err}")
        conn.close()
        return

    if section and section not in SECTION_LABELS:
        _print(f"Unknown section: {section}. Choose from: {', '.join(SECTION_LABELS.keys())}")
        raise typer.Exit(1)

    conn = get_connection()
    interview_console = Console() if HAS_RICH else Console()
    try:
        run_full_interview(interview_console, conn, section=section)
    except (EOFError, KeyboardInterrupt, OSError):
        _print("\nInterview interrupted — terminal may not support interactive prompts.")
        _print("Tip: use 'beacon profile interview --data' for non-interactive mode.")
    finally:
        conn.close()


@profile_app.command("import")
def profile_import(
    file_path: str = typer.Argument(help="Path to JSON file to import"),
):
    """Import profile data from a JSON file."""
    from beacon.importer import import_profile

    conn = get_connection()
    try:
        counts = import_profile(conn, file_path)
    except (FileNotFoundError, ValueError) as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        conn.close()
        raise typer.Exit(1)

    conn.close()

    _print("[green]✓[/green] Profile imported:" if HAS_RICH else "✓ Profile imported:")
    for section, count in counts.items():
        if section != "errors":
            _print(f"  {section}: {count}")
    if "errors" in counts:
        _print(f"\n[yellow]Warnings ({len(counts['errors'])}):[/yellow]" if HAS_RICH else f"\nWarnings ({len(counts['errors'])}):")
        for err in counts["errors"]:
            _print(f"  • {err}")


@profile_app.command("export")
def profile_export(
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Export profile data as JSON for backup."""
    from beacon.importer import export_profile_json

    conn = get_connection()
    content = export_profile_json(conn)
    conn.close()

    if output:
        Path(output).write_text(content)
        _print(f"[green]✓[/green] Profile exported to {output}" if HAS_RICH else f"✓ Profile exported to {output}")
    else:
        print(content)


@profile_app.command("show")
def profile_show(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show full profile summary."""
    from beacon.db.profile import get_education, get_projects, get_publications, get_skills, get_work_experiences

    conn = get_connection()
    work = get_work_experiences(conn)
    projects = get_projects(conn)
    skills = get_skills(conn)
    edu = get_education(conn)
    pubs = get_publications(conn)
    conn.close()

    if as_json:
        _json_out({
            "work_experiences": _rows_to_list(work),
            "projects": _rows_to_list(projects),
            "skills": _rows_to_list(skills),
            "education": _rows_to_list(edu),
            "publications": _rows_to_list(pubs),
        })
        return

    if HAS_RICH:
        console.print(Panel("[bold]Professional Profile Summary[/bold]", style="blue"))
    else:
        print("\nProfessional Profile Summary")

    _print(f"  Work Experiences: {len(work)}")
    _print(f"  Projects:         {len(projects)}")
    _print(f"  Skills:           {len(skills)}")
    _print(f"  Education:        {len(edu)}")
    _print(f"  Publications:     {len(pubs)}")

    if work:
        _print("\n[bold]Recent Work:[/bold]" if HAS_RICH else "\nRecent Work:")
        for exp in work[:3]:
            current = " (current)" if not exp["end_date"] else f" — {exp['end_date']}"
            _print(f"  • {exp['title']} at {exp['company']} ({exp['start_date']}{current})")

    if skills:
        _print(f"\n[bold]Top Skills ({len(skills)}):[/bold]" if HAS_RICH else f"\nTop Skills ({len(skills)}):")
        for s in skills[:10]:
            prof = f" [{s['proficiency']}]" if s["proficiency"] else ""
            _print(f"  • {s['name']}{prof}")


@profile_app.command("work")
def profile_work(
    work_id: int = typer.Argument(None, help="Work experience ID for detail view"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List work experiences or show detail."""
    from beacon.db.profile import get_work_experience_by_id, get_work_experiences

    conn = get_connection()

    if work_id is not None:
        exp = get_work_experience_by_id(conn, work_id)
        conn.close()
        if not exp:
            if as_json:
                _json_out({"error": f"No work experience found with ID {work_id}", "code": 2})
                raise typer.Exit(2)
            _print(f"No work experience found with ID {work_id}")
            return
        if as_json:
            data = _row_to_dict(exp)
            for field in ("key_achievements", "technologies", "metrics"):
                if data.get(field):
                    try:
                        data[field] = json.loads(data[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            _json_out(data)
            return
            _print(f"No work experience found with ID {work_id}")
            return

        if HAS_RICH:
            console.print(Panel(f"[bold]{exp['title']}[/bold] at {exp['company']}", style="blue"))
        else:
            print(f"\n{exp['title']} at {exp['company']}")
        current = "Present" if not exp["end_date"] else exp["end_date"]
        _print(f"  Period: {exp['start_date']} — {current}")
        if exp["description"]:
            _print(f"  {exp['description']}")
        if exp["key_achievements"]:
            _print("\n[bold]Key Achievements:[/bold]" if HAS_RICH else "\nKey Achievements:")
            for a in json.loads(exp["key_achievements"]):
                _print(f"  • {a}")
        if exp["technologies"]:
            techs = json.loads(exp["technologies"])
            _print(f"\n  Technologies: {', '.join(techs)}")
        if exp["metrics"]:
            _print("\n[bold]Metrics:[/bold]" if HAS_RICH else "\nMetrics:")
            for m in json.loads(exp["metrics"]):
                _print(f"  • {m}")
    else:
        exps = get_work_experiences(conn)
        conn.close()

        if as_json:
            _json_out(_rows_to_list(exps))
            return

        if not exps:
            _print("No work experiences recorded.")
            return

        if HAS_RICH:
            table = Table(title="Work Experience")
            table.add_column("ID", style="dim", width=4)
            table.add_column("Company", style="bold")
            table.add_column("Title")
            table.add_column("Period")
            table.add_column("Current")
            for exp in exps:
                current = "Yes" if not exp["end_date"] else ""
                period = f"{exp['start_date']} — {exp['end_date'] or 'Present'}"
                table.add_row(str(exp["id"]), exp["company"], exp["title"], period, current)
            console.print(table)
        else:
            for exp in exps:
                current = " (current)" if not exp["end_date"] else ""
                print(f"  [{exp['id']}] {exp['title']} at {exp['company']}{current}")


@profile_app.command("projects")
def profile_projects(
    project_id: int = typer.Argument(None, help="Project ID for detail view"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List projects or show detail."""
    from beacon.db.profile import get_project_by_id, get_projects

    conn = get_connection()

    if project_id is not None:
        proj = get_project_by_id(conn, project_id)
        conn.close()
        if not proj:
            if as_json:
                _json_out({"error": f"No project found with ID {project_id}", "code": 2})
                raise typer.Exit(2)
            _print(f"No project found with ID {project_id}")
            return

        if as_json:
            data = _row_to_dict(proj)
            for field in ("technologies", "outcomes"):
                if data.get(field):
                    try:
                        data[field] = json.loads(data[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            _json_out(data)
            return

        if HAS_RICH:
            console.print(Panel(f"[bold]{proj['name']}[/bold]", style="blue"))
        else:
            print(f"\n{proj['name']}")
        if proj["description"]:
            _print(f"  {proj['description']}")
        if proj["technologies"]:
            techs = json.loads(proj["technologies"])
            _print(f"  Technologies: {', '.join(techs)}")
        if proj["outcomes"]:
            _print("\n[bold]Outcomes:[/bold]" if HAS_RICH else "\nOutcomes:")
            for o in json.loads(proj["outcomes"]):
                _print(f"  • {o}")
        if proj["repo_url"]:
            _print(f"  Repo: {proj['repo_url']}")
        _print(f"  Public: {'Yes' if proj['is_public'] else 'No'}")
    else:
        projects = get_projects(conn)
        conn.close()

        if as_json:
            _json_out(_rows_to_list(projects))
            return

        if not projects:
            _print("No projects recorded.")
            return

        if HAS_RICH:
            table = Table(title="Projects")
            table.add_column("ID", style="dim", width=4)
            table.add_column("Name", style="bold")
            table.add_column("Public")
            table.add_column("Repo")
            for p in projects:
                table.add_row(str(p["id"]), p["name"],
                              "Yes" if p["is_public"] else "No",
                              p["repo_url"] or "")
            console.print(table)
        else:
            for p in projects:
                pub = " (public)" if p["is_public"] else ""
                print(f"  [{p['id']}] {p['name']}{pub}")


@profile_app.command("skills")
def profile_skills(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List skills grouped by category."""
    from beacon.db.profile import get_skills

    conn = get_connection()
    skills = get_skills(conn)
    conn.close()

    if as_json:
        _json_out(_rows_to_list(skills))
        return

    if not skills:
        _print("No skills recorded.")
        return

    if HAS_RICH:
        table = Table(title="Skills")
        table.add_column("Name", style="bold")
        table.add_column("Category")
        table.add_column("Proficiency")
        table.add_column("Years", justify="right")
        for s in skills:
            table.add_row(
                s["name"],
                s["category"] or "",
                s["proficiency"] or "",
                str(s["years_experience"]) if s["years_experience"] else "",
            )
        console.print(table)
    else:
        current_cat = None
        for s in skills:
            cat = s["category"] or "uncategorized"
            if cat != current_cat:
                print(f"\n  {cat}:")
                current_cat = cat
            prof = f" ({s['proficiency']})" if s["proficiency"] else ""
            print(f"    • {s['name']}{prof}")


@profile_app.command("education")
def profile_education(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List education entries."""
    from beacon.db.profile import get_education

    conn = get_connection()
    edu = get_education(conn)
    conn.close()

    if as_json:
        _json_out(_rows_to_list(edu))
        return

    if not edu:
        _print("No education entries recorded.")
        return

    if HAS_RICH:
        table = Table(title="Education")
        table.add_column("ID", style="dim", width=4)
        table.add_column("Institution", style="bold")
        table.add_column("Degree")
        table.add_column("Field")
        table.add_column("Period")
        for e in edu:
            period = ""
            if e["start_date"]:
                period = f"{e['start_date']} — {e['end_date'] or 'Present'}"
            table.add_row(str(e["id"]), e["institution"],
                          e["degree"] or "", e["field_of_study"] or "", period)
        console.print(table)
    else:
        for e in edu:
            degree = f" — {e['degree']}" if e["degree"] else ""
            field = f" in {e['field_of_study']}" if e["field_of_study"] else ""
            print(f"  [{e['id']}] {e['institution']}{degree}{field}")


@profile_app.command("publications")
def profile_publications(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List publications and talks."""
    from beacon.db.profile import get_publications

    conn = get_connection()
    pubs = get_publications(conn)
    conn.close()

    if as_json:
        _json_out(_rows_to_list(pubs))
        return

    if not pubs:
        _print("No publications or talks recorded.")
        return

    if HAS_RICH:
        table = Table(title="Publications & Talks")
        table.add_column("ID", style="dim", width=4)
        table.add_column("Title", style="bold")
        table.add_column("Type")
        table.add_column("Venue")
        table.add_column("Date")
        for p in pubs:
            table.add_row(str(p["id"]), p["title"], p["pub_type"],
                          p["venue"] or "", p["date_published"] or "")
        console.print(table)
    else:
        for p in pubs:
            venue = f" at {p['venue']}" if p["venue"] else ""
            print(f"  [{p['id']}] [{p['pub_type']}] {p['title']}{venue}")


@profile_app.command("add-presentation")
def profile_add_presentation(
    title: str = typer.Option(..., "--title", "-t", help="Presentation title"),
    abstract: str = typer.Option(None, "--abstract", "-a", help="Presentation abstract"),
    event_name: str = typer.Option(None, "--event", "-e", help="Event name"),
    date: str = typer.Option(None, "--date", "-d", help="Date (YYYY-MM-DD)"),
    audience: str = typer.Option(None, "--audience", help="Target audience"),
    venue: str = typer.Option(None, "--venue", help="Venue name"),
    event_url: str = typer.Option(None, "--url", help="Event URL"),
    duration: int = typer.Option(None, "--duration", help="Duration in minutes"),
    status: str = typer.Option("planned", "--status", "-s", help="Status: planned, accepted, delivered, cancelled"),
    key_points: str = typer.Option(None, "--key-points", help="Key points (comma-separated)"),
    tags: str = typer.Option(None, "--tags", help="Tags (comma-separated)"),
    notes: str = typer.Option(None, "--notes", "-n", help="Notes"),
):
    """Add a presentation to your profile."""
    from beacon.db.speaker import add_presentation

    conn = get_connection()
    kp = [k.strip() for k in key_points.split(",")] if key_points else None
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    pres_id = add_presentation(
        conn, title, abstract=abstract, key_points=kp, event_name=event_name,
        venue=venue, event_url=event_url, date=date, duration_minutes=duration,
        audience=audience, status=status, tags=tag_list, notes=notes,
    )
    conn.close()
    _print(f"[green]✓[/green] Presentation #{pres_id} added" if HAS_RICH else f"✓ Presentation #{pres_id} added")


@profile_app.command("presentations")
def profile_presentations(
    detail: int = typer.Option(None, "--detail", help="Presentation ID for detail view"),
    status: str = typer.Option(None, "--status", "-s", help="Filter by status"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List presentations or show detail."""
    from beacon.db.speaker import get_presentation_by_id, get_presentations

    conn = get_connection()

    if detail is not None:
        pres = get_presentation_by_id(conn, detail)
        conn.close()
        if not pres:
            if as_json:
                _json_out({"error": f"No presentation found with ID {detail}", "code": 2})
                raise typer.Exit(2)
            _print(f"No presentation found with ID {detail}")
            return

        if as_json:
            data = _row_to_dict(pres)
            for field in ("key_points", "co_presenters", "tags"):
                if data.get(field):
                    try:
                        data[field] = json.loads(data[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            _json_out(data)
            return

        if HAS_RICH:
            console.print(Panel(f"[bold]{pres['title']}[/bold]", style="blue"))
        else:
            print(f"\n{pres['title']}")
        _print(f"  Event: {pres['event_name'] or 'N/A'}")
        _print(f"  Venue: {pres['venue'] or 'N/A'}")
        _print(f"  Date: {pres['date'] or 'N/A'}")
        _print(f"  Duration: {pres['duration_minutes'] or 'N/A'} minutes")
        _print(f"  Audience: {pres['audience'] or 'N/A'}")
        _print(f"  Status: {pres['status']}")
        if pres["abstract"]:
            _print("\n[bold]Abstract:[/bold]" if HAS_RICH else "\nAbstract:")
            _print(f"  {pres['abstract']}")
        if pres["key_points"]:
            _print("\n[bold]Key Points:[/bold]" if HAS_RICH else "\nKey Points:")
            for kp in json.loads(pres["key_points"]):
                _print(f"  • {kp}")
        if pres["slides_url"]:
            _print(f"  Slides: {pres['slides_url']}")
        if pres["recording_url"]:
            _print(f"  Recording: {pres['recording_url']}")
        if pres["co_presenters"]:
            co = json.loads(pres["co_presenters"])
            _print(f"  Co-presenters: {', '.join(co)}")
        if pres["tags"]:
            tag_list = json.loads(pres["tags"])
            _print(f"  Tags: {', '.join(tag_list)}")
        if pres["notes"]:
            _print(f"\n  Notes: {pres['notes']}")
    else:
        presentations = get_presentations(conn, status=status)
        conn.close()

        if as_json:
            _json_out(_rows_to_list(presentations))
            return

        if not presentations:
            _print("No presentations recorded.")
            return

        if HAS_RICH:
            table = Table(title="Presentations")
            table.add_column("ID", style="dim", width=4)
            table.add_column("Title", style="bold")
            table.add_column("Event")
            table.add_column("Date")
            table.add_column("Status")
            for p in presentations:
                table.add_row(
                    str(p["id"]),
                    p["title"],
                    p["event_name"] or "",
                    p["date"] or "",
                    p["status"],
                )
            console.print(table)
        else:
            for p in presentations:
                event = f" at {p['event_name']}" if p["event_name"] else ""
                print(f"  [{p['id']}] {p['title']}{event} ({p['status']})")


@profile_app.command("speaker")
def profile_speaker(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show current speaker profile (headshot path and bios)."""
    from beacon.db.speaker import get_speaker_profile

    conn = get_connection()
    profile = get_speaker_profile(conn)
    conn.close()

    if as_json:
        _json_out(_row_to_dict(profile) if profile else {})
        return

    if not profile:
        _print("No speaker profile set. Use 'profile set-headshot' or 'presence bio --save' to create one.")
        return

    if HAS_RICH:
        console.print(Panel("[bold]Speaker Profile[/bold]", style="blue"))
    else:
        print("\nSpeaker Profile")

    _print(f"  Headshot: {profile['headshot_path'] or '(not set)'}")
    if profile["short_bio"]:
        _print("\n[bold]Short Bio:[/bold]" if HAS_RICH else "\nShort Bio:")
        _print(f"  {profile['short_bio']}")
    else:
        _print("  Short Bio: (not set)")
    if profile["long_bio"]:
        _print("\n[bold]Long Bio:[/bold]" if HAS_RICH else "\nLong Bio:")
        _print(f"  {profile['long_bio']}")
    if profile["bio_generated_at"]:
        _print(f"\n  Bio generated: {profile['bio_generated_at']}")


@profile_app.command("set-headshot")
def profile_set_headshot(
    path: str = typer.Argument(help="Path to headshot image file"),
):
    """Set the headshot image path in your speaker profile."""
    from beacon.db.speaker import set_headshot

    resolved = Path(path).resolve()
    if not resolved.exists():
        _print(f"[red]Error:[/red] File not found: {resolved}" if HAS_RICH else f"Error: File not found: {resolved}")
        raise typer.Exit(1)

    conn = get_connection()
    set_headshot(conn, str(resolved))
    conn.close()
    _print(f"[green]✓[/green] Headshot set to {resolved}" if HAS_RICH else f"✓ Headshot set to {resolved}")


@profile_app.command("stats")
def profile_stats(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show profile completeness dashboard."""
    from beacon.db.profile import get_education, get_projects, get_publications, get_skills, get_work_experiences

    conn = get_connection()
    work = get_work_experiences(conn)
    projects = get_projects(conn)
    skills = get_skills(conn)
    edu = get_education(conn)
    pubs = get_publications(conn)
    conn.close()

    sections = [
        ("Work Experiences", len(work), 1),
        ("Projects", len(projects), 2),
        ("Skills", len(skills), 5),
        ("Education", len(edu), 1),
        ("Publications/Talks", len(pubs), 0),
    ]

    filled = sum(1 for _, count, minimum in sections if count >= minimum)
    completeness = int((filled / len(sections)) * 100)

    if as_json:
        skill_categories: dict[str, int] = {}
        for s in skills:
            cat = s["category"] or "uncategorized"
            skill_categories[cat] = skill_categories.get(cat, 0) + 1
        _json_out({
            "completeness_pct": completeness,
            "sections": {label: {"count": count, "minimum": minimum, "met": count >= minimum} for label, count, minimum in sections},
            "skill_categories": skill_categories,
        })
        return

    if HAS_RICH:
        console.print(Panel(f"[bold]Profile Completeness: {completeness}%[/bold]", style="blue"))
    else:
        print(f"\nProfile Completeness: {completeness}%")

    for label, count, minimum in sections:
        if count >= minimum:
            status = "[green]✓[/green]" if HAS_RICH else "✓"
        else:
            status = "[yellow]○[/yellow]" if HAS_RICH else "○"
        _print(f"  {status} {label}: {count}" + (f" (need {minimum})" if count < minimum else ""))

    # Skill category breakdown
    if skills:
        categories: dict[str, int] = {}
        for s in skills:
            cat = s["category"] or "uncategorized"
            categories[cat] = categories.get(cat, 0) + 1
        _print("\n[bold]Skill Categories:[/bold]" if HAS_RICH else "\nSkill Categories:")
        for cat, count in sorted(categories.items()):
            _print(f"  {cat}: {count}")


@profile_app.command("resume")
def profile_resume(
    job_id: int = typer.Argument(help="Job listing ID to tailor resume for"),
    pages: int = typer.Option(1, "--pages", "-p", help="Page limit (1 or 2)"),
    format: str = typer.Option("markdown", "--format", "-f", help="Output format: markdown, pdf, docx"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Generate a tailored resume for a job listing."""
    from beacon.materials.resume import tailor_resume

    conn = get_connection()
    try:
        result = tailor_resume(conn, job_id, page_limit=pages)
    except ValueError as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        conn.close()
        raise typer.Exit(1)
    except RuntimeError as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        conn.close()
        raise typer.Exit(1)
    conn.close()

    if format == "markdown":
        from beacon.materials.renderer import render_markdown
        content = render_markdown(result)
        if output:
            Path(output).write_text(content)
            _print(f"[green]✓[/green] Resume saved to {output}" if HAS_RICH else f"✓ Resume saved to {output}")
        else:
            print(content)
    elif format == "docx":
        from beacon.materials.renderer import render_docx
        out_path = output or f"resume_{job_id}.docx"
        render_docx(result, out_path)
        _print(f"[green]✓[/green] Resume saved to {out_path}" if HAS_RICH else f"✓ Resume saved to {out_path}")
    elif format == "pdf":
        from beacon.materials.renderer import render_pdf
        out_path = output or f"resume_{job_id}.pdf"
        render_pdf(result, out_path)
        _print(f"[green]✓[/green] Resume saved to {out_path}" if HAS_RICH else f"✓ Resume saved to {out_path}")
    else:
        _print(f"Unknown format: {format}. Use markdown, pdf, or docx.")


@profile_app.command("cover-letter")
def profile_cover_letter(
    job_id: int = typer.Argument(help="Job listing ID"),
    tone: str = typer.Option("professional", "--tone", "-t", help="Tone: professional, conversational, technical"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Generate a tailored cover letter for a job listing."""
    from beacon.materials.cover_letter import generate_cover_letter

    conn = get_connection()
    try:
        content = generate_cover_letter(conn, job_id, tone=tone)
    except ValueError as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        conn.close()
        raise typer.Exit(1)
    except RuntimeError as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        conn.close()
        raise typer.Exit(1)
    conn.close()

    if output:
        Path(output).write_text(content)
        _print(f"[green]✓[/green] Cover letter saved to {output}" if HAS_RICH else f"✓ Cover letter saved to {output}")
    else:
        print(content)


# --- Phase 3: Application tracking commands ---

@application_app.command("list")
def application_list(
    status: str = typer.Option(None, "--status", "-s", help="Filter by status"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all applications."""
    from beacon.db.profile import get_applications

    conn = get_connection()
    apps = get_applications(conn, status=status)
    conn.close()

    if as_json:
        _json_out(_rows_to_list(apps))
        return

    if not apps:
        _print("No applications found.")
        return

    if HAS_RICH:
        table = Table(title="Applications")
        table.add_column("ID", style="dim", width=4)
        table.add_column("Company", style="bold")
        table.add_column("Job Title")
        table.add_column("Status")
        table.add_column("Applied")
        table.add_column("Notes", width=30)
        for a in apps:
            table.add_row(
                str(a["id"]),
                a["company_name"],
                a["job_title"],
                a["status"],
                a["applied_date"] or "",
                (a["notes"] or "")[:30],
            )
        console.print(table)
    else:
        for a in apps:
            print(f"  [{a['id']}] {a['company_name']}: {a['job_title']} ({a['status']})")


@application_app.command("show")
def application_show(
    app_id: int = typer.Argument(help="Application ID"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show detailed application info."""
    from beacon.db.profile import get_application_by_id

    conn = get_connection()
    app_row = get_application_by_id(conn, app_id)
    conn.close()

    if not app_row:
        if as_json:
            _json_out({"error": f"No application found with ID {app_id}", "code": 2})
        else:
            _print(f"No application found with ID {app_id}")
        raise typer.Exit(2)

    if as_json:
        _json_out(_row_to_dict(app_row))
        return

    if HAS_RICH:
        console.print(Panel(f"[bold]{app_row['job_title']}[/bold] at {app_row['company_name']}", style="blue"))
        console.print(f"  Status: {app_row['status']}")
        console.print(f"  Applied: {app_row['applied_date'] or 'N/A'}")
        if app_row["resume_path"]:
            console.print(f"  Resume: {app_row['resume_path']}")
        if app_row["cover_letter_path"]:
            console.print(f"  Cover Letter: {app_row['cover_letter_path']}")
        if app_row["notes"]:
            console.print(f"\n[bold]Notes:[/bold]\n  {app_row['notes']}")
    else:
        print(f"\n{app_row['job_title']} at {app_row['company_name']}")
        print(f"  Status: {app_row['status']}")
        print(f"  Applied: {app_row['applied_date'] or 'N/A'}")
        if app_row["notes"]:
            print(f"  Notes: {app_row['notes']}")


@application_app.command("update")
def application_update(
    app_id: int = typer.Argument(help="Application ID"),
    status: str = typer.Option(None, "--status", "-s", help="New status"),
    notes: str = typer.Option(None, "--notes", "-n", help="Update notes"),
):
    """Update application status or notes."""
    from beacon.db.profile import update_application

    conn = get_connection()
    kwargs = {}
    if status:
        kwargs["status"] = status
    if notes:
        kwargs["notes"] = notes

    if not kwargs:
        _print("Provide --status or --notes to update.")
        conn.close()
        return

    success = update_application(conn, app_id, **kwargs)
    conn.close()

    if success:
        _print(f"[green]✓[/green] Application {app_id} updated" if HAS_RICH else f"✓ Application {app_id} updated")
    else:
        _print(f"No application found with ID {app_id}")


# --- Phase 4: Professional Presence commands ---

@presence_app.command("github")
def presence_github_readme(
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Generate a GitHub profile README from your profile data."""
    from beacon.presence.adapters import adapt_for_github_markdown
    from beacon.presence.generator import generate_github_readme

    conn = get_connection()
    _print("Generating GitHub README..." if not HAS_RICH else "[bold]Generating GitHub README...[/bold]")
    try:
        content = generate_github_readme(conn)
        content = adapt_for_github_markdown(content)
    except RuntimeError as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        conn.close()
        raise typer.Exit(1)

    # Save as draft
    from beacon.db.content import add_content_draft
    draft_id = add_content_draft(conn, "readme", "github", "GitHub Profile README", content)
    conn.close()

    if output:
        Path(output).write_text(content)
        _print(f"[green]✓[/green] README saved to {output} (draft #{draft_id})" if HAS_RICH else f"✓ README saved to {output} (draft #{draft_id})")
    else:
        print(content)
        _print(f"\n[dim]Saved as draft #{draft_id}[/dim]" if HAS_RICH else f"\nSaved as draft #{draft_id}")


@presence_app.command("drafts")
def presence_drafts(
    platform: str = typer.Option(None, "--platform", "-p", help="Filter by platform"),
    status: str = typer.Option(None, "--status", "-s", help="Filter by status"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all content drafts."""
    from beacon.db.content import get_content_drafts

    conn = get_connection()
    drafts = get_content_drafts(conn, platform=platform, status=status)
    conn.close()

    if as_json:
        _json_out(_rows_to_list(drafts))
        return

    if not drafts:
        _print("No content drafts found.")
        return

    if HAS_RICH:
        table = Table(title="Content Drafts")
        table.add_column("ID", style="dim", width=4)
        table.add_column("Platform", style="bold")
        table.add_column("Type")
        table.add_column("Title", width=40)
        table.add_column("Status")
        table.add_column("Updated")
        for d in drafts:
            status_color = "green" if d["status"] == "published" else "yellow" if d["status"] == "draft" else "dim"
            table.add_row(
                str(d["id"]),
                d["platform"],
                d["content_type"],
                d["title"][:40],
                f"[{status_color}]{d['status']}[/{status_color}]",
                d["updated_at"][:10] if d["updated_at"] else "",
            )
        console.print(table)
    else:
        for d in drafts:
            print(f"  [{d['id']}] [{d['platform']}] {d['title']} ({d['status']})")


@presence_app.command("draft")
def presence_draft_show(
    draft_id: int = typer.Argument(help="Draft ID"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """View a specific content draft."""
    from beacon.db.content import get_content_draft_by_id

    conn = get_connection()
    draft = get_content_draft_by_id(conn, draft_id)
    conn.close()

    if not draft:
        if as_json:
            _json_out({"error": f"No draft found with ID {draft_id}", "code": 2})
        else:
            _print(f"No draft found with ID {draft_id}")
        raise typer.Exit(2)

    if as_json:
        _json_out(_row_to_dict(draft))
        return

    if HAS_RICH:
        console.print(Panel(
            f"[bold]{draft['title']}[/bold] — {draft['platform']} {draft['content_type']}",
            style="blue",
        ))
        console.print(f"  Status: {draft['status']}")
        console.print(f"  Created: {draft['created_at']}")
        if draft["published_url"]:
            console.print(f"  URL: {draft['published_url']}")
        console.print("")
        console.print(draft["body"])
    else:
        print(f"\n{draft['title']} ({draft['platform']} {draft['content_type']})")
        print(f"  Status: {draft['status']}")
        print(f"\n{draft['body']}")


@presence_app.command("publish")
def presence_draft_publish(
    draft_id: int = typer.Argument(help="Draft ID to publish"),
    url: str = typer.Option(None, "--url", "-u", help="Published URL"),
):
    """Mark a draft as published."""
    from beacon.db.content import publish_content_draft

    conn = get_connection()
    success = publish_content_draft(conn, draft_id, url=url)
    conn.close()

    if success:
        _print(f"[green]✓[/green] Draft {draft_id} marked as published" if HAS_RICH else f"✓ Draft {draft_id} marked as published")
    else:
        _print(f"No draft found with ID {draft_id}")


@presence_app.command("linkedin-headline")
def presence_linkedin_headline():
    """Generate LinkedIn headline options from your profile."""
    from beacon.presence.generator import generate_linkedin_headline

    conn = get_connection()
    _print("Generating LinkedIn headlines..." if not HAS_RICH else "[bold]Generating LinkedIn headlines...[/bold]")
    try:
        content = generate_linkedin_headline(conn)
    except RuntimeError as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        conn.close()
        raise typer.Exit(1)

    from beacon.db.content import add_content_draft
    draft_id = add_content_draft(conn, "headline", "linkedin", "LinkedIn Headline Options", content)
    conn.close()

    print(content)
    _print(f"\n[dim]Saved as draft #{draft_id}[/dim]" if HAS_RICH else f"\nSaved as draft #{draft_id}")


@presence_app.command("linkedin-about")
def presence_linkedin_about():
    """Generate a LinkedIn About section from your profile."""
    from beacon.presence.adapters import adapt_for_linkedin
    from beacon.presence.generator import generate_linkedin_about

    conn = get_connection()
    _print("Generating LinkedIn About..." if not HAS_RICH else "[bold]Generating LinkedIn About...[/bold]")
    try:
        content = generate_linkedin_about(conn)
        content = adapt_for_linkedin(content, max_chars=2600)
    except RuntimeError as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        conn.close()
        raise typer.Exit(1)

    from beacon.db.content import add_content_draft
    draft_id = add_content_draft(conn, "about", "linkedin", "LinkedIn About Section", content)
    conn.close()

    print(content)
    _print(f"\n[dim]Saved as draft #{draft_id}[/dim]" if HAS_RICH else f"\nSaved as draft #{draft_id}")


@presence_app.command("linkedin-post")
def presence_linkedin_post(
    topic: str = typer.Option(..., "--topic", "-t", help="Post topic"),
    tone: str = typer.Option("professional", "--tone", help="Tone: professional, conversational, technical"),
):
    """Generate a LinkedIn post draft on a given topic."""
    from beacon.presence.adapters import adapt_for_linkedin
    from beacon.presence.generator import generate_linkedin_post

    conn = get_connection()
    _print("Generating LinkedIn post..." if not HAS_RICH else "[bold]Generating LinkedIn post...[/bold]")
    try:
        content = generate_linkedin_post(conn, topic, tone=tone)
        content = adapt_for_linkedin(content)
    except RuntimeError as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        conn.close()
        raise typer.Exit(1)

    from beacon.db.content import add_content_draft
    draft_id = add_content_draft(
        conn, "post", "linkedin", f"LinkedIn Post: {topic[:50]}",
        content, metadata={"topic": topic, "tone": tone},
    )
    conn.close()

    print(content)
    _print(f"\n[dim]Saved as draft #{draft_id}[/dim]" if HAS_RICH else f"\nSaved as draft #{draft_id}")


@presence_app.command("blog-outline")
def presence_blog_outline(
    topic: str = typer.Option(..., "--topic", "-t", help="Blog post topic"),
):
    """Generate a blog post outline on a given topic."""
    from beacon.presence.generator import generate_blog_outline

    conn = get_connection()
    _print("Generating blog outline..." if not HAS_RICH else "[bold]Generating blog outline...[/bold]")
    try:
        content = generate_blog_outline(conn, topic)
    except RuntimeError as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        conn.close()
        raise typer.Exit(1)

    from beacon.db.content import add_content_draft
    draft_id = add_content_draft(
        conn, "outline", "blog", f"Blog Outline: {topic[:50]}", content,
        metadata={"topic": topic},
    )
    conn.close()

    print(content)
    _print(f"\n[dim]Saved as draft #{draft_id}[/dim]" if HAS_RICH else f"\nSaved as draft #{draft_id}")


@presence_app.command("blog-generate")
def presence_blog_generate(
    topic: str = typer.Option(..., "--topic", "-t", help="Blog post topic"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Generate a full blog post on a given topic."""
    from beacon.presence.generator import generate_blog_post

    conn = get_connection()
    _print("Generating blog post..." if not HAS_RICH else "[bold]Generating blog post...[/bold]")
    try:
        content = generate_blog_post(conn, topic)
    except RuntimeError as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        conn.close()
        raise typer.Exit(1)

    from beacon.db.content import add_content_draft
    draft_id = add_content_draft(
        conn, "post", "blog", f"Blog Post: {topic[:50]}", content,
        metadata={"topic": topic},
    )
    conn.close()

    if output:
        Path(output).write_text(content)
        _print(f"[green]✓[/green] Blog post saved to {output} (draft #{draft_id})" if HAS_RICH else f"✓ Blog post saved to {output} (draft #{draft_id})")
    else:
        print(content)
        _print(f"\n[dim]Saved as draft #{draft_id}[/dim]" if HAS_RICH else f"\nSaved as draft #{draft_id}")


@presence_app.command("blog-export")
def presence_blog_export(
    draft_id: int = typer.Argument(help="Draft ID to export"),
    format: str = typer.Option("astro", "--format", "-f", help="Export format: astro, medium, devto"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Export a blog draft for a specific platform."""
    from beacon.db.content import get_content_draft_by_id
    from beacon.presence.adapters import adapt_for_blog_markdown, adapt_for_devto, adapt_for_medium

    conn = get_connection()
    draft = get_content_draft_by_id(conn, draft_id)
    conn.close()

    if not draft:
        _print(f"No draft found with ID {draft_id}")
        raise typer.Exit(1)

    metadata = json.loads(draft["metadata"]) if draft["metadata"] else {}

    if format == "astro":
        content = adapt_for_blog_markdown(draft["body"], title=draft["title"])
    elif format == "medium":
        content = adapt_for_medium(draft["body"])
    elif format == "devto":
        content = adapt_for_devto(draft["body"], title=draft["title"],
                                   tags=metadata.get("tags", []))
    else:
        _print(f"Unknown format: {format}. Use astro, medium, or devto.")
        raise typer.Exit(1)

    if output:
        Path(output).write_text(content)
        _print(f"[green]✓[/green] Exported to {output}" if HAS_RICH else f"✓ Exported to {output}")
    else:
        print(content)


@presence_app.command("calendar")
def presence_calendar(
    platform: str = typer.Option(None, "--platform", "-p", help="Filter by platform"),
    status: str = typer.Option(None, "--status", "-s", help="Filter by status"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List content calendar entries."""
    from beacon.db.content import get_calendar_entries

    conn = get_connection()
    entries = get_calendar_entries(conn, platform=platform, status=status)
    conn.close()

    if as_json:
        _json_out(_rows_to_list(entries))
        return

    if not entries:
        _print("No calendar entries found.")
        return

    if HAS_RICH:
        table = Table(title="Content Calendar")
        table.add_column("ID", style="dim", width=4)
        table.add_column("Title", style="bold", width=35)
        table.add_column("Platform")
        table.add_column("Type")
        table.add_column("Target Date")
        table.add_column("Status")
        for e in entries:
            status_color = "green" if e["status"] == "published" else "yellow" if e["status"] == "drafted" else "dim"
            table.add_row(
                str(e["id"]),
                e["title"][:35],
                e["platform"],
                e["content_type"],
                e["target_date"] or "",
                f"[{status_color}]{e['status']}[/{status_color}]",
            )
        console.print(table)
    else:
        for e in entries:
            date = e["target_date"] or "no date"
            print(f"  [{e['id']}] [{e['platform']}] {e['title']} ({e['status']}, {date})")


@presence_app.command("calendar-add")
def presence_calendar_add(
    title: str = typer.Option(..., "--title", "-t", help="Entry title"),
    platform: str = typer.Option(..., "--platform", "-p", help="Target platform"),
    content_type: str = typer.Option("post", "--type", help="Content type"),
    topic: str = typer.Option(None, "--topic", help="Topic"),
    date: str = typer.Option(None, "--date", "-d", help="Target date (YYYY-MM-DD)"),
    notes: str = typer.Option(None, "--notes", "-n", help="Notes"),
):
    """Add a content calendar entry."""
    from beacon.db.content import add_calendar_entry

    conn = get_connection()
    entry_id = add_calendar_entry(
        conn, title, platform, content_type,
        topic=topic, target_date=date, notes=notes,
    )
    conn.close()

    _print(f"[green]✓[/green] Calendar entry #{entry_id} created" if HAS_RICH else f"✓ Calendar entry #{entry_id} created")


@presence_app.command("calendar-seed")
def presence_calendar_seed():
    """Auto-generate calendar entries from content ideas."""
    from beacon.db.content import add_calendar_entry
    from beacon.presence.generator import generate_content_ideas

    conn = get_connection()
    _print("Generating content ideas..." if not HAS_RICH else "[bold]Generating content ideas...[/bold]")
    try:
        ideas = generate_content_ideas(conn)
    except RuntimeError as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        conn.close()
        raise typer.Exit(1)

    # Parse ideas and create calendar entries
    count = 0
    for line in ideas.strip().split("\n"):
        line = line.strip()
        if not line or not line[0].isdigit():
            continue
        # Extract title (everything after "N. " or "N) ")
        title = line.lstrip("0123456789.)")
        title = title.strip(" -:").strip()
        if title:
            add_calendar_entry(conn, title[:100], "blog", "post", topic=title[:100])
            count += 1

    conn.close()
    _print(f"[green]✓[/green] Created {count} calendar entries" if HAS_RICH else f"✓ Created {count} calendar entries")


@presence_app.command("bio")
def presence_bio(
    length: str = typer.Option("short", "--length", "-l", help="Bio length: short or long"),
    save: bool = typer.Option(False, "--save", help="Save the bio to speaker profile"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Generate a speaker bio via LLM."""
    from beacon.presence.generator import generate_speaker_bio_long, generate_speaker_bio_short

    conn = get_connection()
    _print("Generating speaker bio..." if not HAS_RICH else "[bold]Generating speaker bio...[/bold]")
    try:
        if length == "long":
            content = generate_speaker_bio_long(conn)
        else:
            content = generate_speaker_bio_short(conn)
    except RuntimeError as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        conn.close()
        raise typer.Exit(1)

    if save:
        from beacon.db.speaker import set_bio
        if length == "long":
            set_bio(conn, short_bio=content, long_bio=content)
        else:
            set_bio(conn, short_bio=content)
        _print("[green]✓[/green] Bio saved to speaker profile" if HAS_RICH else "✓ Bio saved to speaker profile")

    conn.close()

    if output:
        Path(output).write_text(content)
        _print(f"[green]✓[/green] Bio written to {output}" if HAS_RICH else f"✓ Bio written to {output}")
    else:
        print(content)


@presence_app.command("site-generate")
def presence_site_generate(
    output_dir: str = typer.Option("site/src/content", "--output", "-o", help="Output directory"),
):
    """Generate Astro-ready content files from profile data."""
    from beacon.presence.site import export_site_content

    conn = get_connection()
    _print("Generating site content..." if not HAS_RICH else "[bold]Generating site content...[/bold]")
    try:
        files = export_site_content(conn, output_dir)
    except RuntimeError as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        conn.close()
        raise typer.Exit(1)
    conn.close()

    _print(f"[green]✓[/green] Generated {len(files)} content files:" if HAS_RICH else f"✓ Generated {len(files)} content files:")
    for f in files:
        _print(f"  {f}")


@presence_app.command("site-resume")
def presence_site_resume(
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Generate a resume page for the personal site."""
    from beacon.presence.site import generate_resume_page

    conn = get_connection()
    content = generate_resume_page(conn)
    conn.close()

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(content)
        _print(f"[green]✓[/green] Resume page saved to {output}" if HAS_RICH else f"✓ Resume page saved to {output}")
    else:
        print(content)


@presence_app.command("site-projects")
def presence_site_projects(
    output_dir: str = typer.Option(None, "--output", "-o", help="Output directory"),
):
    """Generate project pages for the personal site."""
    from beacon.db.profile import get_projects
    from beacon.presence.site import generate_project_page

    conn = get_connection()
    projects = get_projects(conn)

    if not projects:
        _print("No projects found in profile.")
        conn.close()
        return

    files = []
    for proj in projects:
        content = generate_project_page(proj)
        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            slug = proj["name"].lower().replace(" ", "-")
            file_path = out_path / f"{slug}.md"
            file_path.write_text(content)
            files.append(str(file_path))
        else:
            print(content)
            print("---")

    conn.close()

    if output_dir:
        _print(f"[green]✓[/green] Generated {len(files)} project pages" if HAS_RICH else f"✓ Generated {len(files)} project pages")


@presence_app.command("enrich")
def presence_enrich(
    work_id: int = typer.Option(None, "--work-id", "-w", help="Work experience ID"),
    list_gaps: bool = typer.Option(False, "--list-gaps", help="List missing profile information"),
    generate_content: bool = typer.Option(False, "--generate-content", help="Generate content from enrichment"),
):
    """Start enrichment interview for accomplishments."""
    from beacon.presence.enrichment import generate_missing_info_todos, run_enrichment_interview

    conn = get_connection()

    if list_gaps:
        gaps = generate_missing_info_todos(conn)
        conn.close()
        if HAS_RICH:
            console.print(Panel("[bold]Profile Gaps & Missing Information[/bold]", style="blue"))
        else:
            print("\nProfile Gaps & Missing Information")
        for gap in gaps:
            _print(f"  {gap}")
        return

    interview_console = Console() if HAS_RICH else Console()
    run_enrichment_interview(interview_console, conn, work_experience_id=work_id, generate_content=generate_content)
    conn.close()


# --- Phase 5: Configuration commands ---

@config_app.command("show")
def config_show(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show current configuration."""
    from beacon.config import load_config
    config = load_config()

    if as_json:
        _json_out({
            "notification_email": config.notification_email,
            "smtp_host": config.smtp_host,
            "smtp_port": config.smtp_port,
            "smtp_user": config.smtp_user,
            "notification_cadence": config.notification_cadence,
            "scan_cadence": config.scan_cadence,
            "min_relevance_alert": config.min_relevance_alert,
            "desktop_notifications": config.desktop_notifications,
            "log_level": config.log_level,
            "log_file": config.log_file,
        })
        return

    if HAS_RICH:
        console.print(Panel("[bold]Beacon Configuration[/bold]", style="blue"))
    else:
        print("\nBeacon Configuration")
    _print(f"  notification_email:     {config.notification_email or '(not set)'}")
    _print(f"  smtp_host:              {config.smtp_host or '(not set)'}")
    _print(f"  smtp_port:              {config.smtp_port}")
    _print(f"  smtp_user:              {config.smtp_user or '(not set)'}")
    _print(f"  smtp_password:          {'****' if config.smtp_password else '(not set)'}")
    _print(f"  notification_cadence:   {config.notification_cadence}")
    _print(f"  scan_cadence:           {config.scan_cadence}")
    _print(f"  min_relevance_alert:    {config.min_relevance_alert}")
    _print(f"  desktop_notifications:  {config.desktop_notifications}")
    _print(f"  log_level:              {config.log_level}")
    _print(f"  log_file:               {config.log_file}")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(help="Configuration key"),
    value: str = typer.Argument(help="New value"),
):
    """Set a configuration value."""
    from beacon.config import get_config_value, load_config, save_config, set_config_value
    config = load_config()
    try:
        set_config_value(config, key, value)
    except KeyError as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        raise typer.Exit(1)
    errors = config.validate()
    if errors:
        _print(f"[yellow]Warning:[/yellow] {'; '.join(errors)}" if HAS_RICH else f"Warning: {'; '.join(errors)}")
    save_config(config)
    _print(f"[green]✓[/green] {key} = {get_config_value(config, key)}" if HAS_RICH else f"✓ {key} = {get_config_value(config, key)}")


@config_app.command("init")
def config_init():
    """Create a default configuration file."""
    from beacon.config import BeaconConfig, save_config
    path = save_config(BeaconConfig())
    _print(f"[green]✓[/green] Configuration file created at {path}" if HAS_RICH else f"✓ Configuration file created at {path}")


# --- Phase 5: Feedback tracking commands ---

@application_app.command("outcome")
def application_outcome(
    app_id: int = typer.Argument(help="Application ID"),
    outcome: str = typer.Option(..., "--outcome", "-o", help="Outcome type: no_response, rejection_auto, rejection_human, phone_screen, technical, onsite, offer, accepted"),
    days: int = typer.Option(None, "--days", "-d", help="Days until response"),
    notes: str = typer.Option(None, "--notes", "-n", help="Notes about the outcome"),
):
    """Record an outcome for an application."""
    from beacon.db.feedback import record_outcome
    conn = get_connection()
    try:
        outcome_id = record_outcome(conn, app_id, outcome, response_days=days, notes=notes)
        _print(f"[green]✓[/green] Outcome recorded (#{outcome_id})" if HAS_RICH else f"✓ Outcome recorded (#{outcome_id})")
    except ValueError as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        raise typer.Exit(1)
    finally:
        conn.close()


@application_app.command("outcomes")
def application_outcomes(
    outcome_filter: str = typer.Option(None, "--outcome", "-o", help="Filter by outcome type"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all recorded outcomes."""
    from beacon.db.feedback import get_outcomes
    conn = get_connection()
    outcomes = get_outcomes(conn, outcome_filter=outcome_filter)
    conn.close()

    if as_json:
        _json_out(_rows_to_list(outcomes))
        return

    if not outcomes:
        _print("No outcomes recorded.")
        return

    if HAS_RICH:
        table = Table(title="Application Outcomes")
        table.add_column("ID", style="dim", width=4)
        table.add_column("App", width=4)
        table.add_column("Outcome", style="bold")
        table.add_column("Days", justify="right")
        table.add_column("Notes", width=40)
        table.add_column("Recorded")
        for o in outcomes:
            table.add_row(
                str(o["id"]),
                str(o["application_id"]),
                o["outcome"],
                str(o["response_days"]) if o["response_days"] else "",
                (o["notes"] or "")[:40],
                o["recorded_at"][:10] if o["recorded_at"] else "",
            )
        console.print(table)
    else:
        for o in outcomes:
            days_str = f" ({o['response_days']}d)" if o["response_days"] else ""
            print(f"  [{o['id']}] App #{o['application_id']}: {o['outcome']}{days_str}")


@application_app.command("effectiveness")
def application_effectiveness(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show resume variant effectiveness analysis."""
    from beacon.db.feedback import get_outcome_stats, get_variant_effectiveness
    conn = get_connection()
    outcome_stats = get_outcome_stats(conn)
    variants = get_variant_effectiveness(conn)
    conn.close()

    if as_json:
        _json_out({
            "outcomes": _rows_to_list(outcome_stats),
            "variants": _rows_to_list(variants),
        })
        return

    stats = outcome_stats

    if HAS_RICH:
        console.print(Panel("[bold]Application Effectiveness[/bold]", style="blue"))
    else:
        print("\nApplication Effectiveness")

    if stats:
        _print("\n[bold]Outcome Distribution:[/bold]" if HAS_RICH else "\nOutcome Distribution:")
        for s in stats:
            _print(f"  {s['outcome']}: {s['count']} (avg {s['avg_days']:.0f}d)" if s["avg_days"] else f"  {s['outcome']}: {s['count']}")
    else:
        _print("  No outcomes recorded yet.")

    if variants:
        _print("\n[bold]Resume Variants:[/bold]" if HAS_RICH else "\nResume Variants:")
        for v in variants:
            _print(f"  {v['variant_label']}: {v['count']} uses")
    else:
        _print("\n  No resume variants tracked yet.")


# --- Phase 5: Dashboard command ---

@app.command()
def dashboard(
    compact: bool = typer.Option(False, "--compact", help="Show compact dashboard"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show the unified Beacon dashboard."""
    from beacon.dashboard import gather_dashboard_data
    conn = get_connection()
    data = gather_dashboard_data(conn)
    conn.close()

    if as_json:
        _json_out(data)
        return

    from beacon.dashboard_render import render_dashboard
    render_dashboard(console if HAS_RICH else None, data, compact=compact)


# --- Phase 5: Notification test command ---

@automation_app.command("test-notify")
def automation_test_notify():
    """Send a test notification."""
    from beacon.config import load_config
    from beacon.notifications.registry import notify_all
    config = load_config()
    results = notify_all(config, "Beacon Test", "This is a test notification from Beacon.", urgency="low")
    if any(results):
        _print("[green]✓[/green] Test notification sent" if HAS_RICH else "✓ Test notification sent")
    else:
        _print("[yellow]⚠[/yellow] No notifications configured or all failed" if HAS_RICH else "⚠ No notifications configured or all failed")


# --- Phase 5: Automation commands ---

@automation_app.command("run")
def automation_run(
    scan_only: bool = typer.Option(False, "--scan-only", help="Only scan for new jobs"),
    digest_only: bool = typer.Option(False, "--digest-only", help="Only send digest"),
):
    """Run an automation cycle."""
    from beacon.automation.runner import run_automation_cycle, run_digest, run_scan_only
    from beacon.config import load_config
    config = load_config()
    conn = get_connection()
    try:
        if scan_only:
            result = run_scan_only(conn, config)
        elif digest_only:
            result = run_digest(conn, config)
        else:
            result = run_automation_cycle(conn, config)
        _print(f"[green]✓[/green] Automation complete: {result['jobs_found']} jobs found, {result['new_relevant_jobs']} relevant" if HAS_RICH else f"✓ Automation complete: {result['jobs_found']} jobs found, {result['new_relevant_jobs']} relevant")
    except Exception as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        raise typer.Exit(1)
    finally:
        conn.close()


@automation_app.command("log")
def automation_log(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of recent entries"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show automation run history."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM automation_log ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()

    if as_json:
        _json_out(_rows_to_list(rows))
        return

    if not rows:
        _print("No automation runs recorded.")
        return

    if HAS_RICH:
        table = Table(title="Automation Log")
        table.add_column("ID", style="dim", width=4)
        table.add_column("Type", style="bold")
        table.add_column("Started")
        table.add_column("Jobs", justify="right")
        table.add_column("Relevant", justify="right")
        table.add_column("Notified", justify="right")
        table.add_column("Duration", justify="right")
        table.add_column("Errors")
        for r in rows:
            duration = f"{r['duration_seconds']:.1f}s" if r["duration_seconds"] else ""
            table.add_row(
                str(r["id"]),
                r["run_type"],
                r["started_at"][:16] if r["started_at"] else "",
                str(r["jobs_found"]),
                str(r["new_relevant_jobs"]),
                str(r["notifications_sent"]),
                duration,
                (r["errors"] or "")[:30],
            )
        console.print(table)
    else:
        for r in rows:
            print(f"  [{r['id']}] {r['run_type']} at {r['started_at']}: {r['jobs_found']} jobs, {r['new_relevant_jobs']} relevant")


@automation_app.command("cron")
def automation_cron(
    action: str = typer.Argument(help="Action: install, uninstall, status"),
    every: int = typer.Option(6, "--every", help="Run every N hours (for install)"),
):
    """Manage cron-based automation scheduling."""
    from beacon.automation.cron_helper import (
        generate_crontab_entry,
        install_crontab,
        show_crontab_status,
        uninstall_crontab,
    )
    if action == "install":
        entry = generate_crontab_entry(every)
        success = install_crontab(entry)
        if success:
            _print(f"[green]✓[/green] Cron installed: every {every} hours" if HAS_RICH else f"✓ Cron installed: every {every} hours")
        else:
            _print("[red]Failed to install crontab[/red]" if HAS_RICH else "Failed to install crontab")
    elif action == "uninstall":
        success = uninstall_crontab()
        if success:
            _print("[green]✓[/green] Cron uninstalled" if HAS_RICH else "✓ Cron uninstalled")
        else:
            _print("[yellow]No beacon cron entry found[/yellow]" if HAS_RICH else "No beacon cron entry found")
    elif action == "status":
        status = show_crontab_status()
        _print(status)
    else:
        _print(f"Unknown action: {action}. Use install, uninstall, or status.")


# --- Phase 5: Agent Orchestration commands ---

@automation_app.command("agents")
def automation_agents(
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan but don't execute"),
):
    """Run all automation agents."""
    from beacon.agents.orchestrator import Orchestrator
    from beacon.config import load_config
    config = load_config()
    conn = get_connection()
    try:
        orchestrator = Orchestrator()
        results = orchestrator.run(conn, config, dry_run=dry_run)
        mode = " (dry run)" if dry_run else ""
        _print(f"[green]✓[/green] Agents complete{mode}: {len(results)} agents ran" if HAS_RICH else f"✓ Agents complete{mode}: {len(results)} agents ran")
        for name, summary in results.items():
            _print(f"  {name}: {summary}")
    except Exception as e:
        _print(f"[red]Error:[/red] {e}" if HAS_RICH else f"Error: {e}")
        raise typer.Exit(1)
    finally:
        conn.close()


@automation_app.command("agents-status")
def automation_agents_status(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show recent agent run summaries."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM automation_log WHERE run_type = 'full' ORDER BY started_at DESC LIMIT 5"
    ).fetchall()
    conn.close()

    if as_json:
        _json_out(_rows_to_list(rows))
        return

    if not rows:
        _print("No agent runs recorded.")
        return

    _print("[bold]Recent Agent Runs:[/bold]" if HAS_RICH else "Recent Agent Runs:")
    for r in rows:
        duration = f" ({r['duration_seconds']:.1f}s)" if r["duration_seconds"] else ""
        status = "[green]OK[/green]" if not r["errors"] else "[red]Error[/red]"
        if not HAS_RICH:
            status = "OK" if not r["errors"] else "Error"
        _print(f"  {r['started_at'][:16]}: {status}{duration} — {r['signals_refreshed']} signals, {r['new_relevant_jobs']} jobs")


# --- Phase 5: Scoring feedback commands ---

@report_app.command("scoring-feedback")
def report_scoring_feedback(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show scoring calibration report."""
    from beacon.research.scoring_calibration import generate_scoring_report
    conn = get_connection()
    report = generate_scoring_report(conn)
    conn.close()
    if as_json:
        _json_out({"content": report})
        return
    print(report)


@report_app.command("variant-effectiveness")
def report_variant_effectiveness(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show resume variant effectiveness report."""
    from beacon.materials.variant_tracker import generate_variant_report
    conn = get_connection()
    report = generate_variant_report(conn)
    conn.close()
    if as_json:
        _json_out({"content": report})
        return
    print(report)


# --- Phase 5: Onboarding command ---

@app.command()
def guide():
    """Show the Beacon onboarding guide."""
    guide_text = """
Getting Started with Beacon
============================

1. Initialize: beacon init
   Set up the database with 38+ AI-first companies.

2. Build Your Profile:
   beacon profile interview     (interactive)
   beacon profile import <file> (from JSON)

3. Configure Preferences:
   beacon config init
   beacon config set notification_email you@example.com
   beacon config set min_relevance_alert 7.0

4. Scan for Jobs:
   beacon scan
   beacon jobs --min-relevance 7.0

5. Review Dashboard:
   beacon dashboard

6. Apply to Jobs:
   beacon job apply <id> --generate
   beacon application outcome <id> --outcome phone_screen

7. Set Up Automation:
   beacon automation cron install --every 6

8. Build Presence:
   beacon presence github
   beacon presence linkedin-post --topic "your topic"
   beacon presence site-generate

Run 'beacon --help' for all commands.
"""
    if HAS_RICH:
        console.print(Panel(guide_text.strip(), title="Beacon Guide", style="blue"))
    else:
        print(guide_text)


# ── Session logging commands ──────────────────────────────────────────


@session_app.command("log")
def session_log(
    title: str = typer.Argument(..., help="Session title"),
    summary: str = typer.Option(..., "--summary", "-s", help="What was accomplished"),
    tag: list[str] = typer.Option([], "--tag", "-t", help="Tags (repeatable)"),
    challenge: list[str] = typer.Option([], "--challenge", "-c", help="Challenges faced (repeatable)"),
    tech: list[str] = typer.Option([], "--tech", help="Technologies used (repeatable)"),
    impact: str = typer.Option(None, "--impact", "-i", help="Impact statement"),
    duration: str = typer.Option(None, "--duration", "-d", help="Estimated duration"),
    project: str = typer.Option("beacon", "--project", "-p", help="Project name"),
    date: str = typer.Option(None, "--date", help="Session date (YYYY-MM-DD)"),
    transcript: str = typer.Option(None, "--transcript", help="Path to transcript file"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Log a Claude Code session with Obsidian note and DB record."""
    from beacon.session import (
        generate_session_note,
        save_session_to_db,
        slugify,
        write_session_note,
    )

    conn = get_connection()

    note_content = generate_session_note(
        title=title,
        summary=summary,
        project=project,
        challenges=challenge or None,
        technologies=tech or None,
        impact=impact,
        tags=tag or None,
        session_date=date,
        duration_estimate=duration,
    )

    obsidian_path = None
    try:
        slug = slugify(title)
        from datetime import date as date_cls
        session_date = date or date_cls.today().isoformat()
        obsidian_path = write_session_note(note_content, session_date, slug)
    except RuntimeError:
        pass  # OBSIDIAN_VAULT_PATH not set — skip note, still save to DB

    session_id = save_session_to_db(
        conn,
        title=title,
        summary=summary,
        project=project,
        challenges=challenge or None,
        technologies=tech or None,
        impact=impact,
        tags=tag or None,
        transcript_path=transcript,
        obsidian_path=obsidian_path,
        duration_estimate=duration,
        session_date=date,
    )
    conn.close()

    result = {"id": session_id, "title": title, "obsidian_path": obsidian_path}
    if as_json:
        print(json.dumps(result))
    else:
        _print(f"Session logged (id={session_id}): {title}")
        if obsidian_path:
            _print(f"  Obsidian note: {obsidian_path}")


@session_app.command("list")
def session_list(
    project: str = typer.Option(None, "--project", "-p", help="Filter by project"),
    tag: str = typer.Option(None, "--tag", "-t", help="Filter by tag"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List logged sessions."""
    from beacon.session import list_sessions

    conn = get_connection()
    sessions = list_sessions(conn, project=project, tag=tag, limit=limit)
    conn.close()

    if as_json:
        print(json.dumps(sessions))
        return

    if not sessions:
        _print("No sessions found.")
        return

    if HAS_RICH:
        table = Table(title="Sessions")
        table.add_column("ID", style="dim")
        table.add_column("Date")
        table.add_column("Project")
        table.add_column("Title")
        table.add_column("Tags")
        for s in sessions:
            table.add_row(
                str(s["id"]),
                s.get("session_date", ""),
                s.get("project", ""),
                s.get("title", ""),
                s.get("tags", ""),
            )
        console.print(table)
    else:
        for s in sessions:
            print(f"{s['id']}: [{s.get('session_date', '')}] {s.get('title', '')}")


@session_app.command("show")
def session_show(
    session_id: int = typer.Argument(..., help="Session ID"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show details for a single session."""
    from beacon.session import get_session

    conn = get_connection()
    session = get_session(conn, session_id)
    conn.close()

    if not session:
        if as_json:
            print(json.dumps({"error": "Session not found", "code": 2}))
        else:
            _print(f"Session {session_id} not found.")
        raise typer.Exit(2)

    if as_json:
        print(json.dumps(session))
        return

    if HAS_RICH:
        details = f"**Project:** {session['project']}\n"
        details += f"**Date:** {session.get('session_date', '')}\n"
        details += f"**Duration:** {session.get('duration_estimate', '') or ''}\n\n"
        details += f"**Summary:** {session['summary']}\n"
        if session.get("challenges"):
            details += f"\n**Challenges:** {session['challenges']}\n"
        if session.get("technologies"):
            details += f"\n**Technologies:** {session['technologies']}\n"
        if session.get("impact"):
            details += f"\n**Impact:** {session['impact']}\n"
        if session.get("tags"):
            details += f"\n**Tags:** {session['tags']}\n"
        if session.get("obsidian_path"):
            details += f"\n**Obsidian:** {session['obsidian_path']}\n"
        console.print(Panel(details, title=session["title"]))
    else:
        print(f"Session {session['id']}: {session['title']}")
        print(f"  Project: {session['project']}")
        print(f"  Summary: {session['summary']}")


# ── Media Log ──────────────────────────────────────────────────────────


@media_app.command("add")
def media_add(
    title: str = typer.Argument(..., help="Title of the video, podcast, or article"),
    source_type: str = typer.Option("video", "--type", "-t", help="Source type: video, podcast, article, talk, course, book"),
    url: str = typer.Option(None, "--url", "-u", help="URL"),
    creator: str = typer.Option(None, "--creator", "-c", help="Creator, channel, or author"),
    platform: str = typer.Option(None, "--platform", "-p", help="Platform (YouTube, Spotify, etc.)"),
    date: str = typer.Option(None, "--date", "-d", help="Date consumed (YYYY-MM-DD)"),
    rating: int = typer.Option(None, "--rating", "-r", help="Rating 1-5"),
    tag: list[str] = typer.Option([], "--tag", help="Tags (repeatable)"),
    takeaways: str = typer.Option(None, "--takeaways", help="Key takeaways"),
    reaction: str = typer.Option(None, "--reaction", help="Personal reaction / feelings"),
    shareable: bool = typer.Option(False, "--shareable", "-s", help="Mark as team-shareable"),
    share_note: str = typer.Option(None, "--share-note", help="Simplified note for team sharing"),
    why_it_matters: str = typer.Option(None, "--why", help="Why this matters to the team / org"),
    quote: list[str] = typer.Option([], "--quote", "-q", help="Key quotes or lines (repeatable)"),
    category: str = typer.Option(None, "--category", help="Share category (e.g. AI Adoption, Leadership)"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Log a video, podcast, article, or other media you consumed."""
    from beacon.media import add_media

    conn = get_connection()
    media_id = add_media(
        conn,
        title=title,
        source_type=source_type,
        url=url,
        creator=creator,
        platform=platform,
        date_consumed=date,
        rating=rating,
        tags=tag or None,
        key_takeaways=takeaways,
        personal_reaction=reaction,
        team_shareable=shareable,
        share_note=share_note,
        why_it_matters=why_it_matters,
        key_quotes=quote or None,
        share_category=category,
    )
    conn.close()

    result = {"id": media_id, "title": title, "source_type": source_type}
    if as_json:
        _json_out(result)
    else:
        _stderr(f"Media logged (id={media_id}): {title}")


@media_app.command("list")
def media_list(
    source_type: str = typer.Option(None, "--type", "-t", help="Filter by source type"),
    tag: str = typer.Option(None, "--tag", help="Filter by tag"),
    min_rating: int = typer.Option(None, "--min-rating", "-r", help="Minimum rating"),
    since: str = typer.Option(None, "--since", help="Since date (YYYY-MM-DD)"),
    search: str = typer.Option(None, "--search", "-s", help="Search title, takeaways, reaction, creator"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max results"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List media log entries with optional filters."""
    from beacon.media import list_media

    conn = get_connection()
    entries = list_media(conn, source_type=source_type, tag=tag, min_rating=min_rating, since=since, search=search, limit=limit)
    conn.close()

    if as_json:
        _json_out(entries)
        return

    if not entries:
        _print("No media entries found.")
        return

    if HAS_RICH:
        table = Table(title="Media Log")
        table.add_column("ID", style="dim")
        table.add_column("Date")
        table.add_column("Type")
        table.add_column("Title")
        table.add_column("Creator")
        table.add_column("Rating")
        table.add_column("Share", style="dim")
        for e in entries:
            stars = "⭐" * e["rating"] if e.get("rating") else ""
            share = "✓" if e.get("team_shareable") else ""
            table.add_row(
                str(e["id"]),
                e.get("date_consumed", "") or "",
                e.get("source_type", ""),
                e.get("title", ""),
                e.get("creator", "") or "",
                stars,
                share,
            )
        console.print(table)
    else:
        for e in entries:
            share = " [shareable]" if e.get("team_shareable") else ""
            print(f"{e['id']}: [{e.get('date_consumed', '')}] {e.get('title', '')}{share}")


@media_app.command("show")
def media_show(
    media_id: int = typer.Argument(..., help="Media entry ID"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show details for a single media entry."""
    from beacon.media import get_media

    conn = get_connection()
    entry = get_media(conn, media_id)
    conn.close()

    if not entry:
        if as_json:
            _json_out({"error": "Media entry not found", "code": 2})
        else:
            _print(f"Media entry {media_id} not found.")
        raise typer.Exit(2)

    if as_json:
        _json_out(entry)
        return

    if HAS_RICH:
        stars = "⭐" * entry["rating"] if entry.get("rating") else "unrated"
        details = f"**Type:** {entry['source_type']}\n"
        details += f"**Creator:** {entry.get('creator') or ''}\n"
        details += f"**Platform:** {entry.get('platform') or ''}\n"
        details += f"**Date:** {entry.get('date_consumed') or ''}\n"
        details += f"**Rating:** {stars}\n"
        if entry.get("url"):
            details += f"**URL:** {entry['url']}\n"
        if entry.get("tags"):
            details += f"**Tags:** {entry['tags']}\n"
        if entry.get("key_takeaways"):
            details += f"\n**Key Takeaways:**\n{entry['key_takeaways']}\n"
        if entry.get("personal_reaction"):
            details += f"\n**Personal Reaction:**\n{entry['personal_reaction']}\n"
        if entry.get("why_it_matters"):
            details += f"\n**Why It Matters:**\n{entry['why_it_matters']}\n"
        if entry.get("key_quotes"):
            details += f"\n**Key Quotes:**\n{entry['key_quotes']}\n"
        if entry.get("share_category"):
            details += f"**Category:** {entry['share_category']}\n"
        if entry.get("team_shareable"):
            details += "\n**Team Shareable:** Yes\n"
            if entry.get("share_note"):
                details += f"**Share Note:** {entry['share_note']}\n"
        console.print(Panel(details, title=entry["title"]))
    else:
        print(f"{entry['title']} ({entry['source_type']})")
        if entry.get("creator"):
            print(f"  Creator: {entry['creator']}")
        if entry.get("key_takeaways"):
            print(f"  Takeaways: {entry['key_takeaways']}")
        if entry.get("personal_reaction"):
            print(f"  Reaction: {entry['personal_reaction']}")


@media_app.command("update")
def media_update(
    media_id: int = typer.Argument(..., help="Media entry ID"),
    takeaways: str = typer.Option(None, "--takeaways", help="Update key takeaways"),
    reaction: str = typer.Option(None, "--reaction", help="Update personal reaction"),
    rating: int = typer.Option(None, "--rating", "-r", help="Update rating 1-5"),
    shareable: bool = typer.Option(None, "--shareable", "-s", help="Mark as team-shareable"),
    share_note: str = typer.Option(None, "--share-note", help="Update share note"),
    why_it_matters: str = typer.Option(None, "--why", help="Update why it matters"),
    quote: list[str] = typer.Option([], "--quote", "-q", help="Replace key quotes (repeatable)"),
    category: str = typer.Option(None, "--category", help="Update share category"),
    tag: list[str] = typer.Option([], "--tag", help="Replace tags (repeatable)"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Update fields on a media entry."""
    from beacon.media import update_media

    kwargs = {}
    if takeaways is not None:
        kwargs["key_takeaways"] = takeaways
    if reaction is not None:
        kwargs["personal_reaction"] = reaction
    if rating is not None:
        kwargs["rating"] = rating
    if shareable is not None:
        kwargs["team_shareable"] = shareable
    if share_note is not None:
        kwargs["share_note"] = share_note
    if why_it_matters is not None:
        kwargs["why_it_matters"] = why_it_matters
    if quote:
        kwargs["key_quotes"] = quote
    if category is not None:
        kwargs["share_category"] = category
    if tag:
        kwargs["tags"] = tag

    if not kwargs:
        if as_json:
            _json_out({"error": "No fields to update", "code": 1})
        else:
            _print("No fields to update. Use --help to see options.")
        raise typer.Exit(1)

    conn = get_connection()
    ok = update_media(conn, media_id, **kwargs)
    conn.close()

    if not ok:
        if as_json:
            _json_out({"error": "Media entry not found", "code": 2})
        else:
            _print(f"Media entry {media_id} not found.")
        raise typer.Exit(2)

    if as_json:
        _json_out({"id": media_id, "updated": True})
    else:
        _stderr(f"Media entry {media_id} updated.")


@media_app.command("team-list")
def media_team_list(
    source_type: str = typer.Option(None, "--type", "-t", help="Filter by source type"),
    tag: str = typer.Option(None, "--tag", help="Filter by tag"),
    min_rating: int = typer.Option(None, "--min-rating", "-r", help="Minimum rating"),
    since: str = typer.Option(None, "--since", help="Since date (YYYY-MM-DD)"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max results"),
    output: str = typer.Option(None, "--output", "-o", help="Write markdown to file"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Export team-shareable media as markdown or JSON for sharing."""
    from beacon.media import export_team_markdown, get_team_list

    conn = get_connection()
    entries = get_team_list(conn, source_type=source_type, tag=tag, min_rating=min_rating, since=since, limit=limit)
    conn.close()

    if as_json:
        _json_out(entries)
        return

    md = export_team_markdown(entries)

    if output:
        Path(output).write_text(md)
        _stderr(f"Team list written to {output}")
    else:
        _print(md)


@media_app.command("export-list")
def media_export_list(
    source_type: str = typer.Option(None, "--type", "-t", help="Filter by source type"),
    tag: str = typer.Option(None, "--tag", help="Filter by tag"),
    min_rating: int = typer.Option(None, "--min-rating", "-r", help="Minimum rating"),
    since: str = typer.Option(None, "--since", help="Since date (YYYY-MM-DD)"),
    category: str = typer.Option(None, "--category", "-c", help="Filter by share category"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max results"),
    fmt: str = typer.Option("json", "--format", "-f", help="Output format: json or csv"),
    output: str = typer.Option(None, "--output", "-o", help="Write to file"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON (same as --format json)"),
):
    """Export team-shareable media for Microsoft Lists / Power Automate.

    Outputs flat rows with columns: Title, URL, Type, Creator, Category,
    WhyItMatters, KeyPoints, KeyQuotes, Rating, Date, Tags, ShareNote.
    """
    from beacon.media import export_for_list, export_list_csv

    conn = get_connection()
    entries = export_for_list(conn, source_type=source_type, tag=tag, min_rating=min_rating, since=since, category=category, limit=limit)
    conn.close()

    if as_json or fmt == "json":
        content = json.dumps(entries, default=str, indent=2)
    else:
        content = export_list_csv(entries)

    if output:
        Path(output).write_text(content)
        _stderr(f"Exported {len(entries)} entries to {output}")
    else:
        print(content)


# ── Network commands ───────────────────────────────────────────────


@network_app.command("add-event")
def network_add_event(
    name: str = typer.Argument(..., help="Event name"),
    organizer: str = typer.Option(None, "--organizer", "-o", help="Organizer or group name"),
    event_type: str = typer.Option("meetup", "--type", "-t", help="Type: meetup, conference, workshop, hackathon, networking, other"),
    url: str = typer.Option(None, "--url", "-u", help="Event URL"),
    location: str = typer.Option(None, "--location", "-l", help="Location"),
    date: str = typer.Option(None, "--date", "-d", help="Date (YYYY-MM-DD)"),
    description: str = typer.Option(None, "--description", help="Description"),
    attendee_count: int = typer.Option(None, "--attendees", help="Approximate attendee count"),
    status: str = typer.Option("upcoming", "--status", "-s", help="Status: upcoming, attended, cancelled, skipped"),
    tag: list[str] = typer.Option([], "--tag", help="Tags (repeatable)"),
    notes: str = typer.Option(None, "--notes", "-n", help="Notes"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Log a networking event (meetup, conference, etc.)."""
    from beacon.network import add_event

    conn = get_connection()
    event_id = add_event(
        conn, name=name, organizer=organizer, event_type=event_type,
        url=url, location=location, date=date, description=description,
        attendee_count=attendee_count, status=status, tags=tag or None, notes=notes,
    )
    conn.close()

    result = {"id": event_id, "name": name, "event_type": event_type, "status": status}
    if as_json:
        _json_out(result)
    else:
        _stderr(f"Event logged (id={event_id}): {name}")


@network_app.command("events")
def network_events(
    status: str = typer.Option(None, "--status", "-s", help="Filter by status"),
    event_type: str = typer.Option(None, "--type", "-t", help="Filter by event type"),
    since: str = typer.Option(None, "--since", help="Since date (YYYY-MM-DD)"),
    search: str = typer.Option(None, "--search", help="Search name, organizer, description"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max results"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List networking events with optional filters."""
    from beacon.network import list_events

    conn = get_connection()
    events = list_events(conn, status=status, event_type=event_type, since=since, search=search, limit=limit)
    conn.close()

    if as_json:
        _json_out(events)
        return

    if not events:
        _print("No events found.")
        return

    if HAS_RICH:
        table = Table(title="Network Events")
        table.add_column("ID", style="dim")
        table.add_column("Date")
        table.add_column("Type")
        table.add_column("Name")
        table.add_column("Organizer")
        table.add_column("Status")
        for e in events:
            table.add_row(
                str(e["id"]),
                e.get("date", "") or "",
                e.get("event_type", ""),
                e.get("name", ""),
                e.get("organizer", "") or "",
                e.get("status", ""),
            )
        console.print(table)
    else:
        for e in events:
            print(f"{e['id']}: [{e.get('date', '')}] {e.get('name', '')} ({e.get('status', '')})")


@network_app.command("event")
def network_event_show(
    event_id: int = typer.Argument(..., help="Event ID"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show event details and linked contacts."""
    from beacon.network import get_event, get_event_contacts

    conn = get_connection()
    event = get_event(conn, event_id)
    if not event:
        conn.close()
        if as_json:
            _json_out({"error": "Event not found", "code": 2})
        else:
            _print(f"Event {event_id} not found.")
        raise typer.Exit(2)

    contacts = get_event_contacts(conn, event_id)
    conn.close()

    if as_json:
        event["contacts"] = contacts
        _json_out(event)
        return

    if HAS_RICH:
        details = f"**Type:** {event['event_type']}\n"
        details += f"**Organizer:** {event.get('organizer') or ''}\n"
        details += f"**Date:** {event.get('date') or ''}\n"
        details += f"**Location:** {event.get('location') or ''}\n"
        details += f"**Status:** {event['status']}\n"
        if event.get("url"):
            details += f"**URL:** {event['url']}\n"
        if event.get("attendee_count"):
            details += f"**Attendees:** ~{event['attendee_count']}\n"
        if event.get("tags"):
            details += f"**Tags:** {event['tags']}\n"
        if event.get("description"):
            details += f"\n{event['description']}\n"
        if event.get("notes"):
            details += f"\n**Notes:** {event['notes']}\n"
        console.print(Panel(details, title=event["name"]))

        if contacts:
            ct = Table(title="Contacts at this event")
            ct.add_column("ID", style="dim")
            ct.add_column("Name")
            ct.add_column("Title")
            ct.add_column("Company")
            ct.add_column("Priority")
            ct.add_column("Follow-up", style="dim")
            for c in contacts:
                prio = "★" * c.get("priority", 0) if c.get("priority") else ""
                fu = "✓" if c.get("followed_up") else (c.get("follow_up") or "")
                ct.add_row(
                    str(c["id"]), c["name"], c.get("title") or "", c.get("company") or "", prio, fu,
                )
            console.print(ct)
        else:
            _print("No contacts linked to this event yet.")
    else:
        print(f"{event['name']} ({event['event_type']}) — {event['status']}")
        if event.get("organizer"):
            print(f"  Organizer: {event['organizer']}")
        for c in contacts:
            print(f"  - {c['name']} ({c.get('title', '')}, {c.get('company', '')})")


@network_app.command("add-contact")
def network_add_contact(
    name: str = typer.Argument(..., help="Contact's full name"),
    title: str = typer.Option(None, "--title", "-t", help="Job title"),
    company: str = typer.Option(None, "--company", "-c", help="Company name"),
    email: str = typer.Option(None, "--email", "-e", help="Email address"),
    linkedin: str = typer.Option(None, "--linkedin", help="LinkedIn profile URL"),
    bio: str = typer.Option(None, "--bio", "-b", help="Short bio"),
    interest: list[str] = typer.Option([], "--interest", "-i", help="Interests (repeatable)"),
    priority: int = typer.Option(0, "--priority", "-p", help="Priority 0-5 (5 = highest)"),
    notes: str = typer.Option(None, "--notes", "-n", help="Notes"),
    event_id: int = typer.Option(None, "--event", help="Link to event ID"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Add a professional contact."""
    from beacon.network import add_contact, link_contact_event

    conn = get_connection()

    # Auto-match company to beacon DB
    company_id = None
    if company:
        row = conn.execute("SELECT id FROM companies WHERE name LIKE ?", (f"%{company}%",)).fetchone()
        if row:
            company_id = row["id"]

    contact_id = add_contact(
        conn, name=name, title=title, company=company, company_id=company_id,
        email=email, linkedin_url=linkedin, bio=bio,
        interests=interest or None, priority=priority, notes=notes,
    )

    if event_id is not None:
        link_contact_event(conn, contact_id, event_id)

    conn.close()

    result = {"id": contact_id, "name": name}
    if company_id:
        result["beacon_company_id"] = company_id
    if event_id is not None:
        result["linked_event_id"] = event_id
    if as_json:
        _json_out(result)
    else:
        extra = f" (matched beacon company #{company_id})" if company_id else ""
        _stderr(f"Contact added (id={contact_id}): {name}{extra}")


@network_app.command("contacts")
def network_contacts(
    company: str = typer.Option(None, "--company", "-c", help="Filter by company name"),
    event_id: int = typer.Option(None, "--event", help="Filter by event ID"),
    min_priority: int = typer.Option(None, "--min-priority", "-p", help="Minimum priority"),
    search: str = typer.Option(None, "--search", "-s", help="Search name, title, company, bio"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max results"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List contacts with optional filters."""
    from beacon.network import list_contacts

    conn = get_connection()
    contacts = list_contacts(conn, company=company, event_id=event_id, min_priority=min_priority, search=search, limit=limit)
    conn.close()

    if as_json:
        _json_out(contacts)
        return

    if not contacts:
        _print("No contacts found.")
        return

    if HAS_RICH:
        table = Table(title="Network Contacts")
        table.add_column("ID", style="dim")
        table.add_column("Name")
        table.add_column("Title")
        table.add_column("Company")
        table.add_column("Priority")
        for c in contacts:
            prio = "★" * c.get("priority", 0) if c.get("priority") else ""
            table.add_row(
                str(c["id"]), c["name"], c.get("title") or "", c.get("company") or "", prio,
            )
        console.print(table)
    else:
        for c in contacts:
            print(f"{c['id']}: {c['name']} — {c.get('title', '')} @ {c.get('company', '')}")


@network_app.command("contact")
def network_contact_show(
    contact_id: int = typer.Argument(..., help="Contact ID"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show contact details and event history."""
    from beacon.network import get_contact, get_contact_events

    conn = get_connection()
    contact = get_contact(conn, contact_id)
    if not contact:
        conn.close()
        if as_json:
            _json_out({"error": "Contact not found", "code": 2})
        else:
            _print(f"Contact {contact_id} not found.")
        raise typer.Exit(2)

    events = get_contact_events(conn, contact_id)

    # Enrich with beacon company info
    beacon_company = None
    if contact.get("company_id"):
        row = conn.execute("SELECT name, ai_first_score, tier FROM companies WHERE id = ?", (contact["company_id"],)).fetchone()
        if row:
            beacon_company = dict(row)
    conn.close()

    if as_json:
        contact["events"] = events
        if beacon_company:
            contact["beacon_company"] = beacon_company
        _json_out(contact)
        return

    if HAS_RICH:
        details = f"**Title:** {contact.get('title') or ''}\n"
        details += f"**Company:** {contact.get('company') or ''}\n"
        if beacon_company:
            details += f"**Beacon Score:** {beacon_company['ai_first_score']} (Tier {beacon_company['tier']})\n"
        if contact.get("email"):
            details += f"**Email:** {contact['email']}\n"
        if contact.get("linkedin_url"):
            details += f"**LinkedIn:** {contact['linkedin_url']}\n"
        if contact.get("priority"):
            details += f"**Priority:** {'★' * contact['priority']}\n"
        if contact.get("interests"):
            details += f"**Interests:** {contact['interests']}\n"
        if contact.get("bio"):
            details += f"\n{contact['bio']}\n"
        if contact.get("notes"):
            details += f"\n**Notes:** {contact['notes']}\n"
        console.print(Panel(details, title=contact["name"]))

        if events:
            et = Table(title="Events attended")
            et.add_column("ID", style="dim")
            et.add_column("Date")
            et.add_column("Event")
            et.add_column("Topics")
            et.add_column("Follow-up")
            for e in events:
                fu = "✓ Done" if e.get("followed_up") else (e.get("follow_up") or "")
                et.add_row(
                    str(e["id"]), e.get("date", "") or "", e["name"],
                    e.get("topics_discussed") or "", fu,
                )
            console.print(et)
    else:
        print(f"{contact['name']} — {contact.get('title', '')} @ {contact.get('company', '')}")
        for e in events:
            print(f"  Event: {e['name']} ({e.get('date', '')})")


@network_app.command("link")
def network_link(
    contact_id: int = typer.Argument(..., help="Contact ID"),
    event_id: int = typer.Argument(..., help="Event ID"),
    topics: str = typer.Option(None, "--topics", "-t", help="Topics discussed"),
    follow_up: str = typer.Option(None, "--follow-up", "-f", help="Follow-up action"),
    notes: str = typer.Option(None, "--notes", "-n", help="Notes"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Link a contact to an event (records that they were there)."""
    from beacon.network import link_contact_event

    conn = get_connection()
    link_id = link_contact_event(conn, contact_id, event_id, topics_discussed=topics, follow_up=follow_up, notes=notes)
    conn.close()

    result = {"id": link_id, "contact_id": contact_id, "event_id": event_id}
    if as_json:
        _json_out(result)
    else:
        _stderr(f"Linked contact {contact_id} to event {event_id}.")


@network_app.command("prep")
def network_prep(
    event_id: int = typer.Argument(..., help="Event ID to prepare for"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Prepare for an event: contacts, company cross-references, talking points."""
    from beacon.network import prep_event

    conn = get_connection()
    prep = prep_event(conn, event_id)
    conn.close()

    if not prep:
        if as_json:
            _json_out({"error": "Event not found", "code": 2})
        else:
            _print(f"Event {event_id} not found.")
        raise typer.Exit(2)

    if as_json:
        _json_out(prep)
        return

    event = prep["event"]
    contacts = prep["contacts"]

    if HAS_RICH:
        header = f"**{event['name']}** — {event.get('date', 'TBD')}\n"
        header += f"Organizer: {event.get('organizer') or 'N/A'} | Location: {event.get('location') or 'N/A'}\n"
        header += f"Contacts: {prep['total_contacts']} | Beacon matches: {prep['beacon_matches']}"
        console.print(Panel(header, title="Event Prep"))

        if contacts:
            ct = Table(title="Who to talk to")
            ct.add_column("Priority", justify="center")
            ct.add_column("Name")
            ct.add_column("Title")
            ct.add_column("Company")
            ct.add_column("Beacon", style="dim")
            ct.add_column("Interests")
            for c in contacts:
                prio = "★" * c.get("priority", 0) if c.get("priority") else "—"
                beacon_info = ""
                if c.get("beacon_company"):
                    bc = c["beacon_company"]
                    beacon_info = f"Score {bc['ai_first_score']} T{bc['tier']}"
                interests = c.get("interests") or ""
                ct.add_row(prio, c["name"], c.get("title") or "", c.get("company") or "", beacon_info, interests)
            console.print(ct)
        else:
            _print("No contacts linked to this event yet. Use [bold]beacon network add-contact --event {event_id}[/bold] to add people.")
    else:
        print(f"Prep: {event['name']} ({event.get('date', 'TBD')})")
        print(f"  Contacts: {prep['total_contacts']}, Beacon matches: {prep['beacon_matches']}")
        for c in contacts:
            bc = f" [Beacon: {c['beacon_company']['ai_first_score']}]" if c.get("beacon_company") else ""
            print(f"  - {c['name']} ({c.get('title', '')}, {c.get('company', '')}){bc}")


def main():
    app()


if __name__ == "__main__":
    main()
