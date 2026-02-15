"""Content generation engine for professional presence.

Generates GitHub READMEs, LinkedIn content, blog posts, and content ideas
using profile data and LLM.
"""

import sqlite3
from datetime import datetime

from beacon.materials.cover_letter import build_profile_summary
from beacon.presence.templates import (
    BLOG_OUTLINE_PROMPT,
    BLOG_OUTLINE_SYSTEM,
    BLOG_POST_PROMPT,
    BLOG_POST_SYSTEM,
    CONTENT_IDEAS_PROMPT,
    CONTENT_IDEAS_SYSTEM,
    ENRICHMENT_CONTENT_ANGLES_PROMPT,
    ENRICHMENT_QUESTIONS_PROMPT,
    ENRICHMENT_SYSTEM,
    GITHUB_README_PROMPT,
    GITHUB_README_SYSTEM,
    LINKEDIN_ABOUT_PROMPT,
    LINKEDIN_ABOUT_SYSTEM,
    LINKEDIN_HEADLINE_PROMPT,
    LINKEDIN_HEADLINE_SYSTEM,
    LINKEDIN_POST_PROMPT,
    LINKEDIN_POST_SYSTEM,
)


def build_full_profile_context(conn: sqlite3.Connection) -> str:
    """Build a comprehensive profile context string for content generation.

    Extends build_profile_summary with additional detail for richer content.
    """
    from beacon.db.profile import (
        get_education,
        get_projects,
        get_publications,
        get_skills,
        get_work_experiences,
    )
    import json

    parts = []

    work = get_work_experiences(conn)
    if work:
        parts.append("Professional Experience:")
        for exp in work:
            current = "Present" if not exp["end_date"] else exp["end_date"]
            parts.append(f"- {exp['title']} at {exp['company']} ({exp['start_date']} — {current})")
            if exp["description"]:
                parts.append(f"  {exp['description']}")
            if exp["key_achievements"]:
                achievements = json.loads(exp["key_achievements"])
                for a in achievements:
                    parts.append(f"  * {a}")
            if exp["technologies"]:
                techs = json.loads(exp["technologies"])
                parts.append(f"  Technologies: {', '.join(techs)}")

    skills = get_skills(conn)
    if skills:
        categories: dict[str, list[str]] = {}
        for s in skills:
            cat = s["category"] or "other"
            categories.setdefault(cat, []).append(
                f"{s['name']} ({s['proficiency']})" if s["proficiency"] else s["name"]
            )
        parts.append("\nSkills:")
        for cat, skill_list in sorted(categories.items()):
            parts.append(f"  {cat}: {', '.join(skill_list)}")

    projects = get_projects(conn)
    if projects:
        parts.append("\nProjects:")
        for p in projects:
            parts.append(f"- {p['name']}: {p['description'] or ''}")
            if p["technologies"]:
                techs = json.loads(p["technologies"])
                parts.append(f"  Technologies: {', '.join(techs)}")
            if p["outcomes"]:
                outcomes = json.loads(p["outcomes"])
                for o in outcomes:
                    parts.append(f"  * {o}")

    edu = get_education(conn)
    if edu:
        parts.append("\nEducation:")
        for e in edu:
            deg = e["degree"] or ""
            field = e["field_of_study"] or ""
            parts.append(f"- {e['institution']}: {deg} {field}".strip())

    pubs = get_publications(conn)
    if pubs:
        parts.append("\nPublications & Talks:")
        for p in pubs:
            venue = f" at {p['venue']}" if p["venue"] else ""
            parts.append(f"- {p['title']}{venue} ({p['pub_type']})")

    return "\n".join(parts)


def generate_github_readme(conn: sqlite3.Connection) -> str:
    """Generate a GitHub profile README from profile data."""
    from beacon.llm.client import generate

    context = build_full_profile_context(conn)
    prompt = GITHUB_README_PROMPT.format(profile_context=context)
    response = generate(prompt, system=GITHUB_README_SYSTEM, temperature=0.7)
    return response.text


def generate_linkedin_headline(conn: sqlite3.Connection) -> str:
    """Generate LinkedIn headline options from profile data."""
    from beacon.llm.client import generate

    context = build_profile_summary(conn)
    prompt = LINKEDIN_HEADLINE_PROMPT.format(profile_context=context)
    response = generate(prompt, system=LINKEDIN_HEADLINE_SYSTEM, temperature=0.8)
    return response.text


def generate_linkedin_about(conn: sqlite3.Connection) -> str:
    """Generate a LinkedIn About section from profile data."""
    from beacon.llm.client import generate

    context = build_full_profile_context(conn)
    prompt = LINKEDIN_ABOUT_PROMPT.format(profile_context=context)
    response = generate(prompt, system=LINKEDIN_ABOUT_SYSTEM, temperature=0.7)
    return response.text


def generate_linkedin_post(conn: sqlite3.Connection, topic: str, tone: str = "professional") -> str:
    """Generate a LinkedIn post draft on a given topic."""
    from beacon.llm.client import generate

    context = build_profile_summary(conn)
    prompt = LINKEDIN_POST_PROMPT.format(topic=topic, tone=tone, profile_context=context)
    response = generate(prompt, system=LINKEDIN_POST_SYSTEM, temperature=0.8)
    return response.text


def generate_blog_outline(conn: sqlite3.Connection, topic: str) -> str:
    """Generate a blog post outline on a given topic."""
    from beacon.llm.client import generate

    context = build_profile_summary(conn)
    prompt = BLOG_OUTLINE_PROMPT.format(topic=topic, profile_context=context)
    response = generate(prompt, system=BLOG_OUTLINE_SYSTEM, temperature=0.7)
    return response.text


def generate_blog_post(conn: sqlite3.Connection, topic: str) -> str:
    """Generate a full blog post on a given topic."""
    from beacon.llm.client import generate

    context = build_full_profile_context(conn)
    date = datetime.now().strftime("%Y-%m-%d")
    prompt = BLOG_POST_PROMPT.format(topic=topic, profile_context=context, date=date)
    response = generate(prompt, system=BLOG_POST_SYSTEM, temperature=0.7, max_tokens=8192)
    return response.text


def generate_content_ideas(conn: sqlite3.Connection) -> str:
    """Generate content ideas for the content calendar."""
    from beacon.llm.client import generate

    context = build_full_profile_context(conn)
    prompt = CONTENT_IDEAS_PROMPT.format(profile_context=context)
    response = generate(prompt, system=CONTENT_IDEAS_SYSTEM, temperature=0.9)
    return response.text


def generate_enrichment_questions(statement: str, work_context: str = "") -> str:
    """Generate follow-up questions for an accomplishment statement."""
    from beacon.llm.client import generate

    prompt = ENRICHMENT_QUESTIONS_PROMPT.format(statement=statement, work_context=work_context)
    response = generate(prompt, system=ENRICHMENT_SYSTEM, temperature=0.6)
    return response.text


def generate_content_angles(enriched_accomplishment: str) -> str:
    """Generate content angles from an enriched accomplishment."""
    from beacon.llm.client import generate

    prompt = ENRICHMENT_CONTENT_ANGLES_PROMPT.format(enriched_accomplishment=enriched_accomplishment)
    response = generate(prompt, system=ENRICHMENT_SYSTEM, temperature=0.7)
    return response.text
