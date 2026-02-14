"""Cover letter generator for Beacon Phase 3.

Integrates Phase 1 company research with profile data to generate
tailored cover letters using LLM.
"""

import json
import sqlite3

from beacon.db.jobs import get_job_by_id
from beacon.db.profile import (
    get_education,
    get_projects,
    get_skills,
    get_work_experiences,
)
from beacon.llm.client import generate
from beacon.llm.prompts import COVER_LETTER_PROMPT, COVER_LETTER_SYSTEM_PROMPT
from beacon.materials.resume import extract_requirements


def build_company_context(conn: sqlite3.Connection, company_id: int) -> str:
    """Build a company context string from Phase 1 research data.

    Pulls leadership signals, AI signals, and tools adopted.
    """
    parts = []

    company = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    if company:
        parts.append(f"Company: {company['name']}")
        if company["description"]:
            parts.append(f"Description: {company['description']}")
        parts.append(f"AI-First Score: {company['ai_first_score']:.1f}/10 (Tier {company['tier']})")
        if company["remote_policy"]:
            parts.append(f"Remote Policy: {company['remote_policy']}")

    # Leadership signals
    leadership = conn.execute(
        "SELECT * FROM leadership_signals WHERE company_id = ? ORDER BY impact_level", (company_id,)
    ).fetchall()
    if leadership:
        parts.append("\nLeadership Signals:")
        for ls in leadership[:5]:
            parts.append(f"- {ls['leader_name']} ({ls['leader_title']}): {ls['content'][:200]}")

    # AI signals
    signals = conn.execute(
        "SELECT * FROM ai_signals WHERE company_id = ? ORDER BY signal_strength DESC", (company_id,)
    ).fetchall()
    if signals:
        parts.append("\nAI Culture Signals:")
        for s in signals[:5]:
            parts.append(f"- [{s['signal_type']}] {s['title']}")

    # Tools adopted
    tools = conn.execute(
        "SELECT * FROM tools_adopted WHERE company_id = ?", (company_id,)
    ).fetchall()
    if tools:
        parts.append("\nAI Tools Adopted:")
        for t in tools:
            parts.append(f"- {t['tool_name']} ({t['adoption_level']})")

    return "\n".join(parts)


def build_profile_summary(conn: sqlite3.Connection) -> str:
    """Build a concise profile summary for cover letter prompts."""
    parts = []

    work = get_work_experiences(conn)
    if work:
        parts.append("Professional Experience:")
        for exp in work[:3]:
            current = "Present" if not exp["end_date"] else exp["end_date"]
            parts.append(f"- {exp['title']} at {exp['company']} ({exp['start_date']} — {current})")
            if exp["key_achievements"]:
                achievements = json.loads(exp["key_achievements"])
                for a in achievements[:2]:
                    parts.append(f"  • {a}")

    skills = get_skills(conn)
    if skills:
        skill_names = [s["name"] for s in skills[:15]]
        parts.append(f"\nKey Skills: {', '.join(skill_names)}")

    projects = get_projects(conn)
    if projects:
        parts.append("\nNotable Projects:")
        for p in projects[:3]:
            parts.append(f"- {p['name']}: {p['description'] or ''}")

    edu = get_education(conn)
    if edu:
        parts.append("\nEducation:")
        for e in edu:
            deg = e["degree"] or ""
            field = e["field_of_study"] or ""
            parts.append(f"- {e['institution']}: {deg} {field}".strip())

    return "\n".join(parts)


def generate_cover_letter(
    conn: sqlite3.Connection,
    job_id: int,
    tone: str = "professional",
) -> str:
    """Generate a tailored cover letter for a specific job listing.

    Tone options: professional, conversational, technical
    """
    job = get_job_by_id(conn, job_id)
    if not job:
        raise ValueError(f"Job listing {job_id} not found")

    # Build context
    company_context = build_company_context(conn, job["company_id"])
    profile_summary = build_profile_summary(conn)

    # Extract requirements
    description = job["description_text"] or job["title"]
    requirements = extract_requirements(description)
    requirements_text = json.dumps(requirements, indent=2)

    # Generate cover letter
    system = COVER_LETTER_SYSTEM_PROMPT.format(tone=tone)
    prompt = COVER_LETTER_PROMPT.format(
        job_title=job["title"],
        company_name=job["company_name"],
        company_context=company_context,
        profile_summary=profile_summary,
        requirements=requirements_text,
        tone=tone,
    )

    response = generate(prompt, system=system, temperature=0.7)
    return response.text
