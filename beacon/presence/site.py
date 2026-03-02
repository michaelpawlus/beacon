"""Personal website data export for Astro-ready content.

Generates markdown content files with YAML frontmatter for an Astro site.
Focus is on data export — minimal Astro scaffolding is provided separately.
"""

import json
import sqlite3
from pathlib import Path

from beacon.db.profile import (
    get_education,
    get_projects,
    get_publications,
    get_skills,
    get_work_experiences,
)


def generate_resume_page(conn: sqlite3.Connection) -> str:
    """Generate a resume/CV page as markdown with YAML frontmatter."""
    work = get_work_experiences(conn)
    skills = get_skills(conn)
    edu = get_education(conn)
    pubs = get_publications(conn)

    parts = [
        "---",
        'title: "Resume"',
        'description: "Professional resume and work history"',
        "layout: ../layouts/Page.astro",
        "---",
        "",
        "# Resume",
        "",
    ]

    # Work Experience
    if work:
        parts.append("## Experience\n")
        for exp in work:
            current = "Present" if not exp["end_date"] else exp["end_date"]
            parts.append(f"### {exp['title']} — {exp['company']}")
            parts.append(f"*{exp['start_date']} to {current}*\n")
            if exp["description"]:
                parts.append(exp["description"])
                parts.append("")
            if exp["key_achievements"]:
                achievements = json.loads(exp["key_achievements"])
                for a in achievements:
                    parts.append(f"- {a}")
                parts.append("")
            if exp["technologies"]:
                techs = json.loads(exp["technologies"])
                parts.append(f"**Technologies:** {', '.join(techs)}\n")

    # Skills
    if skills:
        parts.append("## Skills\n")
        categories: dict[str, list[str]] = {}
        for s in skills:
            cat = s["category"] or "Other"
            cat_display = cat.replace("_", " ").title()
            categories.setdefault(cat_display, []).append(s["name"])
        for cat, skill_list in sorted(categories.items()):
            parts.append(f"**{cat}:** {', '.join(skill_list)}\n")

    # Education
    if edu:
        parts.append("## Education\n")
        for e in edu:
            degree = e["degree"] or ""
            field = e["field_of_study"] or ""
            line = f"### {e['institution']}"
            if degree or field:
                line += f" — {degree} {field}".strip()
            parts.append(line)
            if e["start_date"]:
                end = e["end_date"] or "Present"
                parts.append(f"*{e['start_date']} to {end}*\n")

    # Publications
    if pubs:
        parts.append("## Publications & Talks\n")
        for p in pubs:
            venue = f" — {p['venue']}" if p["venue"] else ""
            date = f" ({p['date_published']})" if p["date_published"] else ""
            parts.append(f"- **{p['title']}**{venue}{date}")
        parts.append("")

    return "\n".join(parts)


def generate_project_page(project: sqlite3.Row) -> str:
    """Generate a project page as markdown with YAML frontmatter."""
    slug = project["name"].lower().replace(" ", "-")

    parts = [
        "---",
        f'title: "{project["name"]}"',
    ]
    if project["description"]:
        desc = project["description"].replace('"', '\\"')
        parts.append(f'description: "{desc}"')
    if project["technologies"]:
        techs = json.loads(project["technologies"])
        parts.append(f"technologies: [{', '.join(techs)}]")
    if project["repo_url"]:
        parts.append(f'repo: "{project["repo_url"]}"')
    parts.append(f"public: {'true' if project['is_public'] else 'false'}")
    parts.append("---")
    parts.append("")

    parts.append(f"# {project['name']}")
    parts.append("")

    if project["description"]:
        parts.append(project["description"])
        parts.append("")

    if project["technologies"]:
        techs = json.loads(project["technologies"])
        parts.append(f"**Built with:** {', '.join(techs)}")
        parts.append("")

    if project["outcomes"]:
        outcomes = json.loads(project["outcomes"])
        parts.append("## Outcomes\n")
        for o in outcomes:
            parts.append(f"- {o}")
        parts.append("")

    if project["repo_url"]:
        parts.append(f"[View on GitHub]({project['repo_url']})")
        parts.append("")

    return "\n".join(parts)


def generate_about_page(conn: sqlite3.Connection) -> str:
    """Generate an about page as markdown with YAML frontmatter."""
    from beacon.db.speaker import get_speaker_profile

    work = get_work_experiences(conn)
    skills = get_skills(conn)
    speaker = get_speaker_profile(conn)

    parts = [
        "---",
        'title: "About"',
        'description: "About me"',
        "layout: ../layouts/Page.astro",
        "---",
        "",
        "# About",
        "",
    ]

    if speaker and speaker["headshot_path"]:
        parts.append(f"![Headshot]({speaker['headshot_path']})")
        parts.append("")

    if speaker and speaker["short_bio"]:
        parts.append(speaker["short_bio"])
        parts.append("")

    if work:
        current = [w for w in work if not w["end_date"]]
        if current:
            exp = current[0]
            parts.append(f"{exp['title']} at {exp['company']}.")
            if exp["description"]:
                parts.append(f"\n{exp['description']}")
            parts.append("")

    if skills:
        categories: dict[str, list[str]] = {}
        for s in skills:
            cat = s["category"] or "Other"
            categories.setdefault(cat, []).append(s["name"])
        parts.append("## What I Work With\n")
        for cat, skill_list in sorted(categories.items()):
            parts.append(f"**{cat.title()}:** {', '.join(skill_list)}\n")

    return "\n".join(parts)


def generate_talks_page(conn: sqlite3.Connection) -> str:
    """Generate a talks/presentations page as markdown with YAML frontmatter."""
    from beacon.db.speaker import get_presentations, get_upcoming_presentations

    upcoming = get_upcoming_presentations(conn)
    all_presentations = get_presentations(conn)
    past = [p for p in all_presentations if p["status"] == "delivered"]

    parts = [
        "---",
        'title: "Talks"',
        'description: "Conference talks and presentations"',
        "layout: ../layouts/Page.astro",
        "---",
        "",
        "# Talks",
        "",
    ]

    if upcoming:
        parts.append("## Upcoming\n")
        for p in upcoming:
            event = f" — {p['event_name']}" if p["event_name"] else ""
            parts.append(f"### {p['title']}{event}")
            if p["date"]:
                parts.append(f"*{p['date']}*\n")
            if p["abstract"]:
                parts.append(p["abstract"])
                parts.append("")
            if p["key_points"]:
                for kp in json.loads(p["key_points"]):
                    parts.append(f"- {kp}")
                parts.append("")

    if past:
        parts.append("## Past Talks\n")
        for p in past:
            event = f" — {p['event_name']}" if p["event_name"] else ""
            parts.append(f"### {p['title']}{event}")
            if p["date"]:
                parts.append(f"*{p['date']}*\n")
            if p["abstract"]:
                parts.append(p["abstract"])
                parts.append("")
            links = []
            if p["slides_url"]:
                links.append(f"[Slides]({p['slides_url']})")
            if p["recording_url"]:
                links.append(f"[Recording]({p['recording_url']})")
            if links:
                parts.append(" | ".join(links))
                parts.append("")

    if not upcoming and not past:
        parts.append("No talks recorded yet.")
        parts.append("")

    return "\n".join(parts)


def export_site_content(conn: sqlite3.Connection, output_dir: str = "site/src/content") -> list[str]:
    """Export all profile data as Astro-ready content files.

    Returns list of file paths created.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = []

    # Resume page
    resume = generate_resume_page(conn)
    resume_path = out / "resume.md"
    resume_path.write_text(resume)
    files.append(str(resume_path))

    # About page
    about = generate_about_page(conn)
    about_path = out / "about.md"
    about_path.write_text(about)
    files.append(str(about_path))

    # Talks page
    talks = generate_talks_page(conn)
    talks_path = out / "talks.md"
    talks_path.write_text(talks)
    files.append(str(talks_path))

    # Project pages
    projects = get_projects(conn)
    if projects:
        projects_dir = out / "projects"
        projects_dir.mkdir(exist_ok=True)
        for proj in projects:
            content = generate_project_page(proj)
            slug = proj["name"].lower().replace(" ", "-")
            file_path = projects_dir / f"{slug}.md"
            file_path.write_text(content)
            files.append(str(file_path))

    return files
