"""Resume tailoring engine for Beacon Phase 3.

Pipeline: extract requirements → select relevant items → tailor via LLM → return structured result.
"""

import json
import sqlite3
from dataclasses import dataclass, field

from beacon.db.jobs import get_job_by_id
from beacon.db.profile import (
    get_education,
    get_projects,
    get_publications,
    get_skills,
    get_work_experiences,
)
from beacon.llm.client import generate, generate_structured
from beacon.llm.prompts import (
    REQUIREMENTS_EXTRACTION_PROMPT,
    RESUME_SYSTEM_PROMPT,
    RESUME_TAILOR_PROMPT,
)


@dataclass
class TailoredResume:
    """Result of the resume tailoring pipeline."""
    job_id: int
    job_title: str
    company_name: str
    markdown: str
    requirements: dict = field(default_factory=dict)


def extract_requirements(job_description: str) -> dict:
    """Extract structured requirements from a job description using LLM."""
    prompt = REQUIREMENTS_EXTRACTION_PROMPT.format(job_description=job_description)
    return generate_structured(prompt, temperature=0.3)


def select_relevant_items(conn: sqlite3.Connection, requirements: dict) -> dict:
    """Select profile items most relevant to the job requirements.

    Returns a dict with filtered profile data.
    """
    required_skills = {s.lower() for s in requirements.get("required_skills", [])}
    preferred_skills = {s.lower() for s in requirements.get("preferred_skills", [])}
    keywords = {k.lower() for k in requirements.get("keywords", [])}
    all_relevant = required_skills | preferred_skills | keywords

    # Get all profile data
    work_exps = get_work_experiences(conn)
    projects = get_projects(conn)
    skills = get_skills(conn)
    edu = get_education(conn)
    pubs = get_publications(conn)

    # Score and filter work experiences by tech overlap
    scored_work = []
    for exp in work_exps:
        techs = set()
        if exp["technologies"]:
            techs = {t.lower() for t in json.loads(exp["technologies"])}
        overlap = len(techs & all_relevant)
        scored_work.append((overlap, exp))
    scored_work.sort(key=lambda x: x[0], reverse=True)

    # Score and filter projects
    scored_projects = []
    for proj in projects:
        techs = set()
        if proj["technologies"]:
            techs = {t.lower() for t in json.loads(proj["technologies"])}
        overlap = len(techs & all_relevant)
        scored_projects.append((overlap, proj))
    scored_projects.sort(key=lambda x: x[0], reverse=True)

    # Filter skills to relevant ones (but include all if few match)
    relevant_skills = []
    other_skills = []
    for skill in skills:
        if skill["name"].lower() in all_relevant:
            relevant_skills.append(skill)
        else:
            other_skills.append(skill)

    # Include all relevant skills + top other skills up to 20
    selected_skills = relevant_skills + other_skills[:max(0, 20 - len(relevant_skills))]

    return {
        "work_experiences": [exp for _, exp in scored_work],
        "projects": [proj for _, proj in scored_projects[:5]],
        "skills": selected_skills,
        "education": list(edu),
        "publications": list(pubs),
    }


def _format_profile_for_prompt(profile_data: dict) -> str:
    """Format selected profile data into a string for the LLM prompt."""
    parts = []

    parts.append("## Work Experience")
    for exp in profile_data.get("work_experiences", []):
        current = "Present" if not exp["end_date"] else exp["end_date"]
        parts.append(f"\n### {exp['title']} at {exp['company']} ({exp['start_date']} — {current})")
        if exp["description"]:
            parts.append(exp["description"])
        if exp["key_achievements"]:
            achievements = json.loads(exp["key_achievements"]) if isinstance(exp["key_achievements"], str) else exp["key_achievements"]
            for a in achievements:
                parts.append(f"- {a}")
        if exp["technologies"]:
            techs = json.loads(exp["technologies"]) if isinstance(exp["technologies"], str) else exp["technologies"]
            parts.append(f"Technologies: {', '.join(techs)}")
        if exp["metrics"]:
            metrics = json.loads(exp["metrics"]) if isinstance(exp["metrics"], str) else exp["metrics"]
            for m in metrics:
                parts.append(f"- {m}")

    parts.append("\n## Projects")
    for proj in profile_data.get("projects", []):
        parts.append(f"\n### {proj['name']}")
        if proj["description"]:
            parts.append(proj["description"])
        if proj["technologies"]:
            techs = json.loads(proj["technologies"]) if isinstance(proj["technologies"], str) else proj["technologies"]
            parts.append(f"Technologies: {', '.join(techs)}")
        if proj["outcomes"]:
            outcomes = json.loads(proj["outcomes"]) if isinstance(proj["outcomes"], str) else proj["outcomes"]
            for o in outcomes:
                parts.append(f"- {o}")

    parts.append("\n## Skills")
    skill_names = [s["name"] for s in profile_data.get("skills", [])]
    parts.append(", ".join(skill_names))

    parts.append("\n## Education")
    for edu in profile_data.get("education", []):
        deg = edu["degree"] or ""
        field = edu["field_of_study"] or ""
        degree = f"{deg} in {field}" if deg and field else deg
        parts.append(f"- {edu['institution']}: {degree}")

    pubs = profile_data.get("publications", [])
    if pubs:
        parts.append("\n## Publications & Talks")
        for pub in pubs:
            venue = f" ({pub['venue']})" if pub["venue"] else ""
            parts.append(f"- [{pub['pub_type']}] {pub['title']}{venue}")

    return "\n".join(parts)


def tailor_resume(conn: sqlite3.Connection, job_id: int, page_limit: int = 1) -> TailoredResume:
    """Generate a tailored resume for a specific job listing.

    Pipeline: extract requirements → select relevant items → tailor via LLM.
    """
    job = get_job_by_id(conn, job_id)
    if not job:
        raise ValueError(f"Job listing {job_id} not found")

    # Extract requirements from job description
    description = job["description_text"] or job["title"]
    requirements = extract_requirements(description)

    # Select relevant profile items
    profile_data = select_relevant_items(conn, requirements)

    # Format profile for LLM
    profile_text = _format_profile_for_prompt(profile_data)
    requirements_text = json.dumps(requirements, indent=2)

    # Generate tailored resume
    prompt = RESUME_TAILOR_PROMPT.format(
        requirements=requirements_text,
        profile=profile_text,
        page_limit=page_limit,
    )
    response = generate(prompt, system=RESUME_SYSTEM_PROMPT, temperature=0.5)

    return TailoredResume(
        job_id=job_id,
        job_title=job["title"],
        company_name=job["company_name"],
        markdown=response.text,
        requirements=requirements,
    )
