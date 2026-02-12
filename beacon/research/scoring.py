"""Scoring algorithm for computing AI-first composite scores.

Composite Score = weighted average of sub-scores:
  - Leadership (30%): How bought-in is leadership?
  - Tool Adoption (25%): How many AI tools, how deeply adopted?
  - Culture (25%): Is AI-first in the DNA, not just a pilot?
  - Evidence Depth (10%): How much evidence do we have?
  - Recency (10%): How recent are the signals?
"""

import math
import sqlite3
from datetime import datetime

# Weights for composite score
WEIGHTS = {
    "leadership": 0.30,
    "tool_adoption": 0.25,
    "culture": 0.25,
    "evidence_depth": 0.10,
    "recency": 0.10,
}

# Signal types that indicate culture vs other categories
CULTURE_SIGNAL_TYPES = {
    "employee_report", "engineering_blog", "job_posting_language",
    "github_activity", "company_policy",
}

# Adoption level scores
ADOPTION_SCORES = {
    "required": 10,
    "encouraged": 8,
    "allowed": 5,
    "exploring": 3,
    "rumored": 1,
}

# Leadership impact scores
IMPACT_SCORES = {
    "company-wide": 10,
    "engineering": 7,
    "team": 4,
    "personal": 2,
}


def compute_leadership_score(conn: sqlite3.Connection, company_id: int) -> float:
    """Score based on leadership signals — CEO-level mandates score highest."""
    rows = conn.execute(
        "SELECT impact_level FROM leadership_signals WHERE company_id = ?",
        (company_id,),
    ).fetchall()
    if not rows:
        return 0.0

    scores = [IMPACT_SCORES.get(r["impact_level"], 2) for r in rows]
    # Take the max impact + bonus for multiple signals
    base = max(scores)
    bonus = min(len(scores) - 1, 3) * 0.5  # up to 1.5 bonus for multiple signals
    return min(base + bonus, 10.0)


def compute_tool_adoption_score(conn: sqlite3.Connection, company_id: int) -> float:
    """Score based on AI tools adopted and depth of adoption."""
    rows = conn.execute(
        "SELECT tool_name, adoption_level FROM tools_adopted WHERE company_id = ?",
        (company_id,),
    ).fetchall()
    if not rows:
        return 0.0

    scores = [ADOPTION_SCORES.get(r["adoption_level"], 1) for r in rows]
    # Best adoption level + diversity bonus
    base = max(scores)
    unique_tools = len(set(r["tool_name"] for r in rows))
    diversity_bonus = min(unique_tools - 1, 4) * 0.5  # up to 2.0 for tool diversity
    return min(base + diversity_bonus, 10.0)


def compute_culture_score(conn: sqlite3.Connection, company_id: int) -> float:
    """Score based on cultural signals — blogs, employee reports, job postings."""
    rows = conn.execute(
        "SELECT signal_type, signal_strength FROM ai_signals WHERE company_id = ? AND signal_type IN ({})".format(
            ",".join("?" * len(CULTURE_SIGNAL_TYPES))
        ),
        (company_id, *CULTURE_SIGNAL_TYPES),
    ).fetchall()
    if not rows:
        return 0.0

    strengths = [r["signal_strength"] or 3 for r in rows]
    avg_strength = sum(strengths) / len(strengths)
    # Scale by number of signals (diminishing returns)
    count_factor = min(math.log2(len(strengths) + 1) / 2.5, 1.0)
    return min(avg_strength * 2 * count_factor, 10.0)


def compute_evidence_depth_score(conn: sqlite3.Connection, company_id: int) -> float:
    """Score based on total amount of evidence across all tables."""
    counts = []
    for table in ["ai_signals", "leadership_signals", "tools_adopted"]:
        row = conn.execute(
            f"SELECT COUNT(*) as cnt FROM {table} WHERE company_id = ?",
            (company_id,),
        ).fetchone()
        counts.append(row["cnt"])

    total = sum(counts)
    if total == 0:
        return 0.0
    # Logarithmic scale — diminishing returns after ~15 signals
    return min(math.log2(total + 1) * 2.5, 10.0)


def compute_recency_score(conn: sqlite3.Connection, company_id: int) -> float:
    """Score based on how recent the evidence is."""
    rows = conn.execute(
        """
        SELECT date_observed FROM ai_signals WHERE company_id = ? AND date_observed IS NOT NULL
        UNION ALL
        SELECT date_observed FROM leadership_signals WHERE company_id = ? AND date_observed IS NOT NULL
        UNION ALL
        SELECT date_observed FROM tools_adopted WHERE company_id = ? AND date_observed IS NOT NULL
        """,
        (company_id, company_id, company_id),
    ).fetchall()

    if not rows:
        return 5.0  # neutral if no dates

    now = datetime.now()
    dates = []
    for r in rows:
        try:
            d = datetime.fromisoformat(r["date_observed"][:10])
            dates.append(d)
        except (ValueError, TypeError):
            continue

    if not dates:
        return 5.0

    most_recent = max(dates)
    days_ago = (now - most_recent).days

    if days_ago <= 30:
        return 10.0
    elif days_ago <= 90:
        return 9.0
    elif days_ago <= 180:
        return 7.0
    elif days_ago <= 365:
        return 5.0
    elif days_ago <= 730:
        return 3.0
    else:
        return 1.0


def compute_composite_score(conn: sqlite3.Connection, company_id: int) -> dict:
    """Compute all sub-scores and the weighted composite for a company."""
    scores = {
        "leadership_score": compute_leadership_score(conn, company_id),
        "tool_adoption_score": compute_tool_adoption_score(conn, company_id),
        "culture_score": compute_culture_score(conn, company_id),
        "evidence_depth_score": compute_evidence_depth_score(conn, company_id),
        "recency_score": compute_recency_score(conn, company_id),
    }

    composite = (
        scores["leadership_score"] * WEIGHTS["leadership"]
        + scores["tool_adoption_score"] * WEIGHTS["tool_adoption"]
        + scores["culture_score"] * WEIGHTS["culture"]
        + scores["evidence_depth_score"] * WEIGHTS["evidence_depth"]
        + scores["recency_score"] * WEIGHTS["recency"]
    )
    scores["composite_score"] = round(composite, 2)
    return scores


def refresh_score(conn: sqlite3.Connection, company_id: int) -> float:
    """Recompute and store the score for a single company. Returns composite."""
    scores = compute_composite_score(conn, company_id)

    # Upsert into score_breakdown
    conn.execute(
        """
        INSERT INTO score_breakdown (company_id, leadership_score, tool_adoption_score,
            culture_score, evidence_depth_score, recency_score, composite_score, last_computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(company_id) DO UPDATE SET
            leadership_score = excluded.leadership_score,
            tool_adoption_score = excluded.tool_adoption_score,
            culture_score = excluded.culture_score,
            evidence_depth_score = excluded.evidence_depth_score,
            recency_score = excluded.recency_score,
            composite_score = excluded.composite_score,
            last_computed_at = excluded.last_computed_at
        """,
        (
            company_id,
            scores["leadership_score"],
            scores["tool_adoption_score"],
            scores["culture_score"],
            scores["evidence_depth_score"],
            scores["recency_score"],
            scores["composite_score"],
        ),
    )

    # Update the main company table
    conn.execute(
        "UPDATE companies SET ai_first_score = ?, updated_at = datetime('now') WHERE id = ?",
        (scores["composite_score"], company_id),
    )
    conn.commit()
    return scores["composite_score"]


def refresh_all_scores(conn: sqlite3.Connection) -> int:
    """Recompute scores for all companies. Returns count updated."""
    rows = conn.execute("SELECT id FROM companies").fetchall()
    for row in rows:
        refresh_score(conn, row["id"])
    return len(rows)
