"""Resume variant tracking and effectiveness analysis."""

import sqlite3
from datetime import datetime


def analyze_variant_performance(conn: sqlite3.Connection) -> dict:
    """Analyze how different resume variants perform in terms of outcomes."""
    data = conn.execute(
        """SELECT rv.variant_label, ao.outcome, ao.response_days
           FROM resume_variants rv
           JOIN applications a ON rv.application_id = a.id
           LEFT JOIN application_outcomes ao ON a.id = ao.application_id
           ORDER BY rv.variant_label"""
    ).fetchall()

    if not data:
        return {"has_data": False, "message": "No variant data available. Track resume variants to enable analysis."}

    positive_outcomes = {"phone_screen", "technical", "onsite", "offer", "accepted"}
    variants = {}

    for row in data:
        label = row["variant_label"]
        if label not in variants:
            variants[label] = {"total": 0, "positive": 0, "outcomes": []}
        variants[label]["total"] += 1
        if row["outcome"] in positive_outcomes:
            variants[label]["positive"] += 1
        if row["outcome"]:
            variants[label]["outcomes"].append(row["outcome"])

    result = {"has_data": True, "variants": {}}
    for label, stats in variants.items():
        rate = (stats["positive"] / stats["total"] * 100) if stats["total"] > 0 else 0
        result["variants"][label] = {
            "total_uses": stats["total"],
            "positive_outcomes": stats["positive"],
            "success_rate": round(rate, 1),
            "outcomes": stats["outcomes"],
        }

    return result


def suggest_variant_for_job(conn: sqlite3.Connection, job_id: int) -> str | None:
    """Suggest the best resume variant for a job based on historical performance."""
    performance = analyze_variant_performance(conn)
    if not performance.get("has_data"):
        return None

    # Find variant with highest success rate (with at least 2 uses)
    best_variant = None
    best_rate = -1
    for label, stats in performance["variants"].items():
        if stats["total_uses"] >= 2 and stats["success_rate"] > best_rate:
            best_rate = stats["success_rate"]
            best_variant = label

    return best_variant


def generate_variant_report(conn: sqlite3.Connection) -> str:
    """Generate a markdown variant effectiveness report."""
    analysis = analyze_variant_performance(conn)

    lines = ["# Resume Variant Effectiveness Report", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]

    if not analysis.get("has_data"):
        lines.append(analysis.get("message", "No data available."))
        lines.append("")
        lines.append("To start tracking variants, use:")
        lines.append("  beacon application outcome <id> --outcome <type>")
        return "\n".join(lines)

    lines.append("## Variant Performance")
    lines.append("")
    lines.append("| Variant | Uses | Positive | Rate |")
    lines.append("|---------|------|----------|------|")
    for label, stats in sorted(analysis["variants"].items(), key=lambda x: x[1]["success_rate"], reverse=True):
        lines.append(f"| {label} | {stats['total_uses']} | {stats['positive_outcomes']} | {stats['success_rate']}% |")

    # Suggestion
    best = suggest_variant_for_job(conn, 0)  # job_id doesn't matter for suggestion
    if best:
        lines.append("")
        lines.append("## Recommendation")
        lines.append(f"Best performing variant: **{best}**")

    return "\n".join(lines)
