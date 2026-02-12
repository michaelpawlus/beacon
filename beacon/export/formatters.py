"""Export formatters for Beacon data — Markdown report, CSV, JSON."""

import csv
import io
import json
import sqlite3
from datetime import datetime


def export_markdown_table(conn: sqlite3.Connection, min_score: float | None = None) -> str:
    """Export a simple markdown table of companies."""
    rows = _get_companies(conn, min_score)
    tier_labels = {1: "AI-Native", 2: "Convert", 3: "Strong", 4: "Emerging"}
    lines = ["# AI-First Company Index", ""]
    lines.append("| Rank | Company | Score | Tier | Remote | Industry |")
    lines.append("|------|---------|-------|------|--------|----------|")
    for i, r in enumerate(rows, 1):
        lines.append(
            f"| {i} | **{r['name']}** | {r['ai_first_score']:.1f} | "
            f"{tier_labels.get(r['tier'], '?')} | {r['remote_policy']} | {r['industry']} |"
        )
    return "\n".join(lines)


def export_csv(conn: sqlite3.Connection, min_score: float | None = None) -> str:
    """Export company data as CSV."""
    rows = _get_companies(conn, min_score)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["rank", "name", "score", "tier", "remote_policy", "industry", "careers_url"])
    for i, r in enumerate(rows, 1):
        writer.writerow([i, r["name"], r["ai_first_score"], r["tier"],
                        r["remote_policy"], r["industry"], r["careers_url"]])
    return buf.getvalue()


def export_json(conn: sqlite3.Connection, min_score: float | None = None) -> str:
    """Export company data as JSON."""
    rows = _get_companies(conn, min_score)
    data = []
    for i, r in enumerate(rows, 1):
        data.append({
            "rank": i, "name": r["name"], "score": r["ai_first_score"],
            "tier": r["tier"], "remote_policy": r["remote_policy"],
            "industry": r["industry"], "careers_url": r["careers_url"],
        })
    return json.dumps(data, indent=2)


def export_report(conn: sqlite3.Connection) -> str:
    """Generate a full blog-ready markdown report of AI-first companies."""
    now = datetime.now().strftime("%B %Y")
    tier_labels = {1: "AI-Native", 2: "AI-First Convert", 3: "Strong AI Adoption", 4: "Emerging Signals"}
    tier_descriptions = {
        1: "These companies build AI or were founded on AI-first principles. AI isn't a feature — it's the entire company.",
        2: "These companies have made public, leadership-driven shifts to AI-first operations. CEO mandates, hiring freezes replaced by AI, and measurable culture change.",
        3: "Significant AI integration in engineering culture and products. Strong adoption signals even if not explicitly mandated from the top.",
        4: "Companies showing promising signals of AI adoption. More research needed, but the direction is clear.",
    }
    tier_emoji = {1: "🟢", 2: "🔵", 3: "🟡", 4: "⚪"}

    lines = [
        f"# The AI-First Company Index ({now})",
        "",
        "> A curated, evidence-backed ranking of companies where AI tools aren't just",
        "> allowed — they're expected. Every entry includes public evidence of leadership",
        "> buy-in, tool adoption, and cultural integration.",
        "",
        "---",
        "",
        "## Methodology",
        "",
        "Each company is scored on a 0–10 scale across five dimensions:",
        "",
        "| Dimension | Weight | What It Measures |",
        "|-----------|--------|------------------|",
        "| **Leadership Buy-in** | 30% | Has the CEO/CTO publicly committed to AI-first operations? |",
        "| **Tool Adoption** | 25% | Which AI tools are required, encouraged, or allowed? |",
        "| **Culture** | 25% | Is AI-first in the DNA? Engineering blogs, employee reports, job postings. |",
        "| **Evidence Depth** | 10% | How much verifiable evidence do we have? |",
        "| **Recency** | 10% | How recent are the signals? |",
        "",
        "The composite score is a weighted average of these dimensions. All evidence",
        "is sourced from public, verifiable URLs (company blogs, news articles, social",
        "media posts, job listings).",
        "",
    ]

    stats = _get_stats(conn)
    lines.extend([
        "**Database at a glance:**",
        f"- {stats['companies']} companies tracked across 4 tiers",
        f"- {stats['total_signals']} total signals collected",
        f"- {stats['leadership']} leadership signals from CEOs and CTOs",
        f"- {stats['tools']} AI tool adoption data points",
        "",
        "---",
        "",
    ])

    for tier in [1, 2, 3, 4]:
        companies = conn.execute(
            "SELECT * FROM companies WHERE tier = ? ORDER BY ai_first_score DESC",
            (tier,),
        ).fetchall()

        if not companies:
            continue

        lines.append(f"## {tier_emoji[tier]} Tier {tier}: {tier_labels[tier]}")
        lines.append("")
        lines.append(tier_descriptions[tier])
        lines.append("")

        for c in companies:
            scores = conn.execute(
                "SELECT * FROM score_breakdown WHERE company_id = ?", (c["id"],)
            ).fetchone()

            leadership = conn.execute(
                "SELECT * FROM leadership_signals WHERE company_id = ? ORDER BY date_observed DESC",
                (c["id"],),
            ).fetchall()

            tools = conn.execute(
                "SELECT * FROM tools_adopted WHERE company_id = ?", (c["id"],)
            ).fetchall()

            signals = conn.execute(
                "SELECT * FROM ai_signals WHERE company_id = ? ORDER BY signal_strength DESC LIMIT 3",
                (c["id"],),
            ).fetchall()

            lines.append(f"### {c['name']} — {c['ai_first_score']:.1f}/10")
            lines.append("")

            meta_parts = []
            if c["industry"]:
                meta_parts.append(c["industry"])
            if c["hq_location"]:
                meta_parts.append(c["hq_location"])
            if c["remote_policy"]:
                meta_parts.append(c["remote_policy"])
            if c["size_bucket"]:
                meta_parts.append(c["size_bucket"])
            if meta_parts:
                lines.append(f"*{' · '.join(meta_parts)}*")
                lines.append("")

            if c["description"]:
                lines.append(c["description"])
                lines.append("")

            if scores:
                lines.append("**Score Breakdown:**")
                lines.append(f"Leadership: {scores['leadership_score']:.1f} · "
                           f"Tools: {scores['tool_adoption_score']:.1f} · "
                           f"Culture: {scores['culture_score']:.1f} · "
                           f"Evidence: {scores['evidence_depth_score']:.1f} · "
                           f"Recency: {scores['recency_score']:.1f}")
                lines.append("")

            if leadership:
                lines.append("**Key Leadership Signals:**")
                for ls in leadership[:2]:
                    content = ls["content"][:200]
                    lines.append(f"- **{ls['leader_name']}** ({ls['leader_title']}): \"{content}\"")
                lines.append("")

            if tools:
                tool_strs = [f"{t['tool_name']} ({t['adoption_level']})" for t in tools]
                lines.append(f"**Tools:** {', '.join(tool_strs)}")
                lines.append("")

            if signals:
                lines.append("**Notable Signals:**")
                for s in signals:
                    strength = "★" * (s["signal_strength"] or 0)
                    url_part = f" ([source]({s['source_url']}))" if s["source_url"] else ""
                    lines.append(f"- [{strength}] {s['title']}{url_part}")
                lines.append("")

            if c["careers_url"]:
                lines.append(f"[Careers page]({c['careers_url']})")
                lines.append("")

            lines.append("---")
            lines.append("")

    lines.extend([
        "## About This Index",
        "",
        "This index is maintained by [Beacon](https://github.com/michaelpawlus/beacon),",
        "an open-source AI-first company intelligence platform. The data is collected",
        "from public sources and scored algorithmically.",
        "",
        "**Contributing:** Know about a company's AI adoption that isn't tracked here?",
        "Open an issue or submit a PR with the evidence URL.",
        "",
        f"*Last updated: {now}*",
    ])

    return "\n".join(lines)


def _get_companies(conn, min_score=None):
    query = "SELECT * FROM companies"
    params = []
    if min_score:
        query += " WHERE ai_first_score >= ?"
        params.append(min_score)
    query += " ORDER BY ai_first_score DESC"
    return conn.execute(query, params).fetchall()


def _get_stats(conn):
    return {
        "companies": conn.execute("SELECT COUNT(*) as cnt FROM companies").fetchone()["cnt"],
        "total_signals": (
            conn.execute("SELECT COUNT(*) as cnt FROM ai_signals").fetchone()["cnt"]
            + conn.execute("SELECT COUNT(*) as cnt FROM leadership_signals").fetchone()["cnt"]
            + conn.execute("SELECT COUNT(*) as cnt FROM tools_adopted").fetchone()["cnt"]
        ),
        "leadership": conn.execute("SELECT COUNT(*) as cnt FROM leadership_signals").fetchone()["cnt"],
        "tools": conn.execute("SELECT COUNT(*) as cnt FROM tools_adopted").fetchone()["cnt"],
    }
