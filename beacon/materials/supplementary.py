"""Supplementary application materials for Beacon Phase 3.

Generates "Why this company?" statements and portfolio summaries
using Phase 1 AI-first signals and profile data.
"""

import json
import sqlite3

from beacon.db.jobs import get_job_by_id
from beacon.db.profile import get_projects
from beacon.llm.client import generate
from beacon.llm.prompts import PORTFOLIO_SUMMARY_PROMPT, WHY_STATEMENT_PROMPT
from beacon.materials.cover_letter import build_company_context, build_profile_summary
from beacon.materials.resume import extract_requirements


def generate_why_statement(conn: sqlite3.Connection, job_id: int) -> str:
    """Generate a 'Why this company?' statement using Phase 1 AI-first signals."""
    job = get_job_by_id(conn, job_id)
    if not job:
        raise ValueError(f"Job listing {job_id} not found")

    company_context = build_company_context(conn, job["company_id"])
    profile_summary = build_profile_summary(conn)

    prompt = WHY_STATEMENT_PROMPT.format(
        company_name=job["company_name"],
        company_context=company_context,
        profile_summary=profile_summary,
    )
    response = generate(prompt, temperature=0.7)
    return response.text


def generate_portfolio_summary(conn: sqlite3.Connection, job_id: int) -> str:
    """Generate a portfolio summary matching projects to job requirements."""
    job = get_job_by_id(conn, job_id)
    if not job:
        raise ValueError(f"Job listing {job_id} not found")

    description = job["description_text"] or job["title"]
    requirements = extract_requirements(description)
    requirements_text = json.dumps(requirements, indent=2)

    projects = get_projects(conn)
    projects_text = []
    for p in projects:
        entry = f"### {p['name']}"
        if p["description"]:
            entry += f"\n{p['description']}"
        if p["technologies"]:
            techs = json.loads(p["technologies"])
            entry += f"\nTechnologies: {', '.join(techs)}"
        if p["outcomes"]:
            outcomes = json.loads(p["outcomes"])
            entry += "\nOutcomes: " + "; ".join(outcomes)
        projects_text.append(entry)

    prompt = PORTFOLIO_SUMMARY_PROMPT.format(
        requirements=requirements_text,
        projects="\n\n".join(projects_text),
    )
    response = generate(prompt, temperature=0.5)
    return response.text
