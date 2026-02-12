"""Beacon CLI — AI-First Company Intelligence Database.

Usage:
    beacon init              Initialize the database with seed data
    beacon companies         List all companies sorted by AI-first score
    beacon show <name>       Show detailed info for a company
    beacon scores refresh    Recompute all company scores
    beacon export markdown   Export company rankings as markdown
    beacon export csv        Export company data as CSV
    beacon stats             Show database statistics
"""

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
    else:
        print(f"\n{row['name']} — Score: {row['ai_first_score']:.1f}/10, Tier: {row['tier']}")
        print(f"  {row['description']}")


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


def main():
    app()


if __name__ == "__main__":
    main()
