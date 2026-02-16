"""Scoring calibration — correlates relevance scores with application outcomes."""

import sqlite3
from datetime import datetime


def compute_calibration_adjustments(conn: sqlite3.Connection) -> dict:
    """Analyze how relevance scores correlate with outcomes.

    Returns calibration data including score ranges for each outcome type.
    Does NOT auto-change weights — generates a report for user review.
    """
    feedback = conn.execute(
        """SELECT ao.outcome, j.relevance_score, ao.response_days
           FROM application_outcomes ao
           JOIN applications a ON ao.application_id = a.id
           JOIN job_listings j ON a.job_id = j.id
           ORDER BY j.relevance_score DESC"""
    ).fetchall()

    if not feedback:
        return {
            "has_data": False,
            "message": "No outcome data available. Record application outcomes to enable calibration.",
        }

    positive_outcomes = {"phone_screen", "technical", "onsite", "offer", "accepted"}
    negative_outcomes = {"no_response", "rejection_auto", "rejection_human"}

    positive_scores = [f["relevance_score"] for f in feedback if f["outcome"] in positive_outcomes]
    negative_scores = [f["relevance_score"] for f in feedback if f["outcome"] in negative_outcomes]

    result = {
        "has_data": True,
        "total_outcomes": len(feedback),
        "positive_count": len(positive_scores),
        "negative_count": len(negative_scores),
    }

    if positive_scores:
        result["positive_avg_score"] = sum(positive_scores) / len(positive_scores)
        result["positive_min_score"] = min(positive_scores)
        result["positive_max_score"] = max(positive_scores)
    if negative_scores:
        result["negative_avg_score"] = sum(negative_scores) / len(negative_scores)

    # Score by outcome type
    outcome_scores = {}
    for f in feedback:
        outcome = f["outcome"]
        if outcome not in outcome_scores:
            outcome_scores[outcome] = []
        outcome_scores[outcome].append(f["relevance_score"])

    result["by_outcome"] = {
        outcome: {
            "count": len(scores),
            "avg_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
        }
        for outcome, scores in outcome_scores.items()
    }

    # Suggestions
    suggestions = []
    if positive_scores and negative_scores:
        pos_avg = result["positive_avg_score"]
        neg_avg = result["negative_avg_score"]
        if pos_avg < neg_avg + 1.0:
            suggestions.append(
                "Positive outcomes don't strongly correlate with higher scores. "
                "Consider reviewing scoring weights."
            )
        if result.get("positive_min_score", 0) < 5.0:
            suggestions.append(
                f"Some positive outcomes came from low-scored jobs (min: {result['positive_min_score']:.1f}). "
                "Your scoring may be undervaluing certain job attributes."
            )
    if len(feedback) < 10:
        suggestions.append("Accumulate more outcome data (10+) for reliable calibration.")

    result["suggestions"] = suggestions
    return result


def generate_scoring_report(conn: sqlite3.Connection) -> str:
    """Generate a markdown scoring calibration report."""
    cal = compute_calibration_adjustments(conn)

    lines = ["# Scoring Calibration Report", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]

    if not cal["has_data"]:
        lines.append(cal["message"])
        return "\n".join(lines)

    lines.append("## Summary")
    lines.append(f"- Total outcomes: {cal['total_outcomes']}")
    lines.append(f"- Positive outcomes: {cal['positive_count']}")
    lines.append(f"- Negative outcomes: {cal['negative_count']}")

    if "positive_avg_score" in cal:
        lines.append(f"- Positive avg score: {cal['positive_avg_score']:.1f}")
    if "negative_avg_score" in cal:
        lines.append(f"- Negative avg score: {cal['negative_avg_score']:.1f}")

    lines.append("")
    lines.append("## By Outcome Type")
    for outcome, stats in cal.get("by_outcome", {}).items():
        lines.append(
            f"- **{outcome}**: {stats['count']} "
            f"({stats['avg_score']:.1f} avg, {stats['min_score']:.1f}-{stats['max_score']:.1f})"
        )

    if cal.get("suggestions"):
        lines.append("")
        lines.append("## Suggestions")
        for s in cal["suggestions"]:
            lines.append(f"- {s}")

    return "\n".join(lines)
