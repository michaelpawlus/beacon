"""Interview prep brief generator.

Takes one row from `beacon match-jobs --with-outcomes --json`, joins it with
company research, the global skill-gap table, optional stack-quest arc
suggestion, and the user's profile, and renders a per-job vault note.

Deterministic. No LLM calls in v1 — the brief is a structured prep workspace,
not a hallucinated dossier. A v2 `--enhance` flag can layer LLM commentary on
top.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import yaml

from beacon.db.profile import get_projects, get_work_experiences
from beacon.materials.company_context import build_company_context_dict

_QUESTIONS_PATH = Path(__file__).parent / "questions" / "base.yaml"


ROLE_FAMILY_KEYWORDS = {
    # Order matters — first match wins, so put more specific roles first.
    "manager": ("manager", "director", "head of"),
    "architect": ("architect",),
    "scientist": ("scientist", "researcher"),
    "analyst": ("analyst",),
    "engineer": ("engineer", "developer", "swe"),
}


def detect_role_family(title: str | None) -> str:
    """Return the role family slug used to pick prep questions."""
    if not title:
        return "default"
    lc = title.lower()
    for family, needles in ROLE_FAMILY_KEYWORDS.items():
        for needle in needles:
            if needle in lc:
                return family
    return "default"


def load_question_templates(path: Path | None = None) -> dict[str, list[str]]:
    """Load the YAML question templates. ``path`` overrides for tests."""
    target = path or _QUESTIONS_PATH
    with open(target) as f:
        return yaml.safe_load(f) or {}


def pick_questions(title: str | None, templates: dict[str, list[str]]) -> list[str]:
    """Return the question list for a job title, falling back to ``default``."""
    family = detect_role_family(title)
    return list(templates.get(family) or templates.get("default") or [])


def _safe_json_list(value: Any) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []


def _profile_talking_points(
    conn: sqlite3.Connection,
    match_keywords: list[str],
    limit: int = 3,
) -> list[dict]:
    """Pick work + project rows with the highest skill overlap to ``match_keywords``.

    No LLM — pure DB join scored by lowercased token overlap.
    """
    keywords = {k.lower() for k in match_keywords if k}
    candidates: list[tuple[int, dict]] = []

    for row in get_work_experiences(conn):
        techs = {t.lower() for t in _safe_json_list(row["technologies"])}
        achievements = _safe_json_list(row["key_achievements"])
        overlap = len(techs & keywords)
        # Tiebreaker: current roles + presence of achievements bump score
        score = overlap * 10 + (1 if row["end_date"] is None else 0) + (1 if achievements else 0)
        candidates.append((
            score,
            {
                "kind": "work",
                "title": row["title"],
                "company": row["company"],
                "achievement": achievements[0] if achievements else None,
                "overlap": sorted(techs & keywords),
            },
        ))

    for row in get_projects(conn):
        techs = {t.lower() for t in _safe_json_list(row["technologies"])}
        outcomes = _safe_json_list(row["outcomes"])
        overlap = len(techs & keywords)
        score = overlap * 10 + (1 if row["is_public"] else 0)
        candidates.append((
            score,
            {
                "kind": "project",
                "title": row["name"],
                "company": None,
                "achievement": outcomes[0] if outcomes else (row["description"] or None),
                "overlap": sorted(techs & keywords),
            },
        ))

    # Drop zero-overlap rows unless we'd otherwise return nothing
    nonzero = [c for c in candidates if c[0] > 0]
    pool = nonzero or candidates
    pool.sort(key=lambda c: c[0], reverse=True)
    return [c[1] for c in pool[:limit]]


def _dynamic_questions(company_ctx: dict) -> list[str]:
    """Build 0–2 extra questions from leadership / AI signals."""
    questions: list[str] = []
    for ls in company_ctx.get("leadership_signals", []):
        leader = ls.get("leader_name")
        if leader:
            questions.append(
                f"I noticed {leader}'s public statement on {ls.get('signal_type') or 'AI direction'} — "
                "how has that translated into how the team works day-to-day?"
            )
            break
    signals = company_ctx.get("ai_signals", [])
    for s in signals:
        if (s.get("signal_strength") or 0) >= 4:
            questions.append(
                f'"{s.get("title")}" caught my eye as a strong signal of how this team thinks about AI. '
                "Where does that show up in the work this role would own?"
            )
            break
    return questions[:2]


def pick_arc(arcs: list[dict] | None, missing: list[str]) -> dict | None:
    """Pick the first stack-quest arc whose ``target_skill`` matches a missing skill."""
    if not arcs or not missing:
        return None
    missing_lc = {m.lower() for m in missing}
    for arc in arcs:
        target = (arc.get("target_skill") or arc.get("skill") or "").lower()
        if target and target in missing_lc:
            return arc
    return None


def build_brief(
    conn: sqlite3.Connection,
    match_row: dict,
    gaps: list[dict] | None = None,
    arc_suggestion: dict | None = None,
    *,
    question_templates: dict[str, list[str]] | None = None,
) -> dict:
    """Compose the structured brief payload from existing data sources."""
    gaps = gaps or []
    templates = question_templates if question_templates is not None else load_question_templates()

    job_id = match_row.get("job_id")
    job_row = None
    company_ctx: dict = {"company": None, "leadership_signals": [], "ai_signals": [], "tools": []}
    if job_id is not None:
        job_row = conn.execute(
            "SELECT j.*, c.id AS c_id, c.name AS company_name FROM job_listings j "
            "JOIN companies c ON j.company_id = c.id WHERE j.id = ?",
            (job_id,),
        ).fetchone()
        if job_row:
            company_ctx = build_company_context_dict(conn, job_row["c_id"])

    gap_index = {g["skill_name"].lower(): g for g in gaps if g.get("skill_name")}
    missing = list(match_row.get("missing") or [])
    gap_analysis = []
    for skill in missing:
        g = gap_index.get(skill.lower())
        gap_analysis.append({
            "skill": skill,
            "status": (g or {}).get("status"),
            "priority": (g or {}).get("priority"),
            "demand_count": (g or {}).get("demand_count"),
        })

    talking_points = _profile_talking_points(
        conn,
        match_keywords=missing + list(match_row.get("reasons") or []),
    )

    base_questions = pick_questions(match_row.get("title"), templates)
    dyn_questions = _dynamic_questions(company_ctx)

    return {
        "job_id": job_id,
        "company": match_row.get("company"),
        "title": match_row.get("title"),
        "location": match_row.get("location") or (job_row["location"] if job_row else None),
        "fit_score": match_row.get("fit_score"),
        "sub_scores": match_row.get("sub_scores") or {},
        "reasons": list(match_row.get("reasons") or []),
        "missing": missing,
        "url": match_row.get("url"),
        "status": match_row.get("status"),
        "company_context": company_ctx,
        "gap_analysis": gap_analysis,
        "arc": arc_suggestion,
        "talking_points": talking_points,
        "prep_questions": base_questions + dyn_questions,
    }


def _fmt_score(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "—"


def render_brief_markdown(brief: dict) -> str:
    """Render the brief into the 8-section markdown body."""
    lines: list[str] = []
    company = brief.get("company") or "Unknown company"
    title = brief.get("title") or "Unknown role"

    lines.append(f"# Interview Brief — {company}: {title}\n")

    # 1. Snapshot
    lines.append("## Snapshot")
    company_row = brief["company_context"].get("company") or {}
    tier = company_row.get("tier")
    ai_score = company_row.get("ai_first_score")
    snapshot = [
        f"- **Company:** {company}",
        f"- **Role:** {title}",
        f"- **Location:** {brief.get('location') or '—'}",
        f"- **Fit score:** {_fmt_score(brief.get('fit_score'))} / 10",
        f"- **AI-first tier:** {tier if tier is not None else '—'}"
        + (f" (score {ai_score:.1f})" if isinstance(ai_score, (int, float)) else ""),
    ]
    url = brief.get("url")
    if url:
        snapshot.append(f"- **Listing:** {url}")
    lines.extend(snapshot)
    lines.append("")

    # 2. Why this matches
    lines.append("## Why this matches")
    reasons = brief.get("reasons") or []
    if reasons:
        for r in reasons:
            lines.append(f"- {r}")
    else:
        lines.append("- No fit reasons recorded.")
    sub = brief.get("sub_scores") or {}
    if sub:
        lines.append("")
        lines.append("**Sub-scores:**")
        for key, val in sub.items():
            lines.append(f"- `{key}`: {_fmt_score(val)}")
    lines.append("")

    # 3. Company posture
    lines.append("## Company posture")
    ctx = brief["company_context"]
    if company_row.get("description"):
        lines.append(f"_{company_row['description']}_\n")
    if ctx.get("leadership_signals"):
        lines.append("**Leadership signals:**")
        for ls in ctx["leadership_signals"]:
            leader = ls.get("leader_name") or "?"
            leader_title = ls.get("leader_title") or ""
            content = (ls.get("content") or "")[:200]
            lines.append(f"- {leader} ({leader_title}): {content}")
        lines.append("")
    if ctx.get("ai_signals"):
        lines.append("**AI culture signals:**")
        for s in ctx["ai_signals"]:
            lines.append(f"- [{s.get('signal_type')}] {s.get('title')}")
        lines.append("")
    if ctx.get("tools"):
        lines.append("**Tools adopted:**")
        for t in ctx["tools"]:
            lines.append(f"- {t.get('tool_name')} ({t.get('adoption_level')})")
        lines.append("")
    if not (ctx.get("leadership_signals") or ctx.get("ai_signals") or ctx.get("tools")):
        lines.append("_No research signals on file for this company yet._\n")

    # 4. Gap analysis
    lines.append("## Gap analysis")
    if brief["gap_analysis"]:
        for g in brief["gap_analysis"]:
            bits = [f"**{g['skill']}**"]
            if g.get("status"):
                bits.append(f"status: {g['status']}")
            if g.get("demand_count") is not None:
                bits.append(f"demand: {g['demand_count']}")
            if g.get("priority") is not None:
                bits.append(f"priority: {g['priority']}")
            lines.append(f"- {' · '.join(bits)}")
    else:
        lines.append("- No missing skills surfaced by the matcher.")
    lines.append("")

    # 5. Suggested next move
    lines.append("## Suggested next move")
    arc = brief.get("arc")
    if arc:
        arc_id = arc.get("id") or arc.get("arc_id") or arc.get("slug") or "?"
        time_est = arc.get("time_estimate") or arc.get("duration") or "—"
        why = arc.get("why") or arc.get("rationale") or arc.get("description") or ""
        target = arc.get("target_skill") or arc.get("skill") or ""
        lines.append(f"- **Arc:** `{arc_id}`")
        if target:
            lines.append(f"- **Target skill:** {target}")
        lines.append(f"- **Time estimate:** {time_est}")
        if why:
            lines.append(f"- **Why this arc:** {why}")
    else:
        lines.append(
            "- No stack-quest arc matched these gaps. Run `stack-quest arcs suggest --json` "
            "to refresh suggestions."
        )
    lines.append("")

    # 6. Talking points
    lines.append("## Talking points")
    if brief["talking_points"]:
        for tp in brief["talking_points"]:
            head = tp["title"]
            if tp.get("company"):
                head += f" — {tp['company']}"
            overlap = ", ".join(tp.get("overlap") or [])
            achievement = tp.get("achievement")
            line = f"- **{head}**"
            if overlap:
                line += f" (overlaps: {overlap})"
            lines.append(line)
            if achievement:
                lines.append(f"  - {achievement}")
    else:
        lines.append("- _No matching work/projects yet. Run `beacon profile interview` to fill in._")
    lines.append("")

    # 7. Prep questions
    lines.append("## Prep questions to ask")
    for q in brief["prep_questions"]:
        lines.append(f"- [ ] {q}")
    lines.append("")

    # 8. Application checklist
    lines.append("## Application checklist")
    lines.append("- [ ] Tailor resume (`beacon profile resume <job_id>`)")
    lines.append("- [ ] Draft cover letter (`beacon profile cover-letter <job_id>`)")
    lines.append("- [ ] Submit application (`beacon job apply <job_id>`)")
    lines.append("- [ ] Log phone screen outcome (`beacon application outcome ...`)")
    lines.append("- [ ] Log onsite / technical outcome")
    lines.append("- [ ] Send thank-you note within 24 hours")
    lines.append("")

    return "\n".join(lines)
