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
profile_app = typer.Typer(help="Professional profile management")
application_app = typer.Typer(help="Application tracking")
presence_app = typer.Typer(help="Professional presence & content generation")
app.add_typer(job_app, name="job")
app.add_typer(report_app, name="report")
app.add_typer(profile_app, name="profile")
app.add_typer(application_app, name="application")
app.add_typer(presence_app, name="presence")
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
            from beacon.materials.resume import tailor_resume
            from beacon.materials.renderer import render_markdown
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


# --- Phase 3: Profile commands ---

@profile_app.command("interview")
def profile_interview(
    section: str = typer.Option(None, "--section", "-s", help="Interview section: work, projects, skills, education, publications"),
):
    """Interactive interview to build your professional profile."""
    from beacon.interview import SECTION_LABELS, run_full_interview

    if section and section not in SECTION_LABELS:
        _print(f"Unknown section: {section}. Choose from: {', '.join(SECTION_LABELS.keys())}")
        raise typer.Exit(1)

    conn = get_connection()
    interview_console = Console() if HAS_RICH else Console()
    run_full_interview(interview_console, conn, section=section)
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
def profile_show():
    """Show full profile summary."""
    from beacon.db.profile import get_education, get_projects, get_publications, get_skills, get_work_experiences

    conn = get_connection()
    work = get_work_experiences(conn)
    projects = get_projects(conn)
    skills = get_skills(conn)
    edu = get_education(conn)
    pubs = get_publications(conn)
    conn.close()

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
):
    """List work experiences or show detail."""
    from beacon.db.profile import get_work_experience_by_id, get_work_experiences

    conn = get_connection()

    if work_id is not None:
        exp = get_work_experience_by_id(conn, work_id)
        conn.close()
        if not exp:
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
):
    """List projects or show detail."""
    from beacon.db.profile import get_project_by_id, get_projects

    conn = get_connection()

    if project_id is not None:
        proj = get_project_by_id(conn, project_id)
        conn.close()
        if not proj:
            _print(f"No project found with ID {project_id}")
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
def profile_skills():
    """List skills grouped by category."""
    from beacon.db.profile import get_skills

    conn = get_connection()
    skills = get_skills(conn)
    conn.close()

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
def profile_education():
    """List education entries."""
    from beacon.db.profile import get_education

    conn = get_connection()
    edu = get_education(conn)
    conn.close()

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
def profile_publications():
    """List publications and talks."""
    from beacon.db.profile import get_publications

    conn = get_connection()
    pubs = get_publications(conn)
    conn.close()

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


@profile_app.command("stats")
def profile_stats():
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

    total = sum(count for _, count, _ in sections)
    filled = sum(1 for _, count, minimum in sections if count >= minimum)
    completeness = int((filled / len(sections)) * 100)

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
):
    """List all applications."""
    from beacon.db.profile import get_applications

    conn = get_connection()
    apps = get_applications(conn, status=status)
    conn.close()

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
def application_show(app_id: int = typer.Argument(help="Application ID")):
    """Show detailed application info."""
    from beacon.db.profile import get_application_by_id

    conn = get_connection()
    app_row = get_application_by_id(conn, app_id)
    conn.close()

    if not app_row:
        _print(f"No application found with ID {app_id}")
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
    from beacon.presence.generator import generate_github_readme
    from beacon.presence.adapters import adapt_for_github_markdown

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
):
    """List all content drafts."""
    from beacon.db.content import get_content_drafts

    conn = get_connection()
    drafts = get_content_drafts(conn, platform=platform, status=status)
    conn.close()

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
):
    """View a specific content draft."""
    from beacon.db.content import get_content_draft_by_id

    conn = get_connection()
    draft = get_content_draft_by_id(conn, draft_id)
    conn.close()

    if not draft:
        _print(f"No draft found with ID {draft_id}")
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
    from beacon.presence.generator import generate_linkedin_about
    from beacon.presence.adapters import adapt_for_linkedin

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
    from beacon.presence.generator import generate_linkedin_post
    from beacon.presence.adapters import adapt_for_linkedin

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
):
    """List content calendar entries."""
    from beacon.db.content import get_calendar_entries

    conn = get_connection()
    entries = get_calendar_entries(conn, platform=platform, status=status)
    conn.close()

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
    from beacon.presence.generator import generate_content_ideas
    from beacon.db.content import add_calendar_entry

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
    from beacon.presence.site import generate_project_page
    from beacon.db.profile import get_projects

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


def main():
    app()


if __name__ == "__main__":
    main()
