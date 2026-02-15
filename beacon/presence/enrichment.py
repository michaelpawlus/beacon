"""Enrichment interview system for accomplishment capture.

Guides the user through structured STAR interviews to capture
professional accomplishments in rich detail, then generates
multi-platform content from enriched data.
"""

import json
import sqlite3

from beacon.db.content import add_accomplishment, add_content_draft, get_accomplishments
from beacon.db.profile import (
    get_education,
    get_projects,
    get_publications,
    get_skills,
    get_work_experience_by_id,
    get_work_experiences,
)


def generate_missing_info_todos(conn: sqlite3.Connection) -> list[str]:
    """Generate a list of missing profile information as TODO items."""
    todos = []

    work = get_work_experiences(conn)
    skills = get_skills(conn)
    edu = get_education(conn)
    pubs = get_publications(conn)
    projects = get_projects(conn)

    # Education check
    if not edu:
        todos.append("[ ] Add education entries (institution, degree, field of study)")

    # Work experience quality checks
    if not work:
        todos.append("[ ] Add work experiences")
    else:
        for exp in work:
            if not exp["key_achievements"]:
                todos.append(f"[ ] Add key achievements for {exp['title']} at {exp['company']}")
            elif exp["key_achievements"]:
                achievements = json.loads(exp["key_achievements"])
                if len(achievements) < 3:
                    todos.append(f"[ ] Add more achievements for {exp['title']} at {exp['company']} (have {len(achievements)}, recommend 3+)")
            if not exp["technologies"]:
                todos.append(f"[ ] Add technologies for {exp['title']} at {exp['company']}")
            if not exp["metrics"]:
                todos.append(f"[ ] Add quantified metrics for {exp['title']} at {exp['company']}")
            if not exp["description"]:
                todos.append(f"[ ] Add description for {exp['title']} at {exp['company']}")

    # Skills check
    if len(skills) < 10:
        todos.append(f"[ ] Add more skills (have {len(skills)}, recommend 10+)")

    skill_categories = set(s["category"] for s in skills if s["category"])
    expected_categories = {"language", "framework", "tool", "domain"}
    missing_cats = expected_categories - skill_categories
    if missing_cats:
        todos.append(f"[ ] Add skills in categories: {', '.join(missing_cats)}")

    # Projects check
    if not projects:
        todos.append("[ ] Add project entries")
    else:
        public_projects = [p for p in projects if p["is_public"]]
        if not public_projects:
            todos.append("[ ] Add at least one public project with repo URL")

    # Publications check
    if not pubs:
        todos.append("[ ] Add publications, talks, or conference presentations")

    # Accomplishments enrichment check
    accomplishments = get_accomplishments(conn)
    if not accomplishments:
        todos.append("[ ] Run enrichment interviews to capture detailed accomplishments")
    else:
        incomplete = [a for a in accomplishments if not a["result"] or not a["metrics"]]
        if incomplete:
            todos.append(f"[ ] Complete enrichment for {len(incomplete)} accomplishment(s) missing results/metrics")

    if not todos:
        todos.append("[x] Profile looks complete! Consider running enrichment interviews for deeper content.")

    return todos


def run_enrichment_interview(
    console,
    conn: sqlite3.Connection,
    work_experience_id: int | None = None,
    generate_content: bool = False,
) -> dict | None:
    """Run an interactive enrichment interview to capture an accomplishment.

    Returns the enriched accomplishment data dict, or None if cancelled.
    """
    from rich.prompt import Confirm, Prompt

    console.print("\n[bold]Enrichment Interview[/bold]")
    console.print("Let's capture a professional accomplishment in detail.\n")

    # If work_experience_id specified, show context
    work_context = ""
    if work_experience_id:
        exp = get_work_experience_by_id(conn, work_experience_id)
        if exp:
            console.print(f"[dim]Context: {exp['title']} at {exp['company']}[/dim]\n")
            work_context = f"{exp['title']} at {exp['company']}"

    # Get the raw accomplishment statement
    statement = Prompt.ask("Describe an accomplishment (one sentence)")
    if not statement:
        console.print("[yellow]No statement provided. Exiting.[/yellow]")
        return None

    # STAR framework questions
    console.print("\n[bold]Let's dig deeper (STAR framework):[/bold]\n")

    context = Prompt.ask("Situation: What was the challenge or opportunity?", default="")
    action = Prompt.ask("Action: What did you specifically do?", default="")
    result = Prompt.ask("Result: What was the outcome?", default="")
    metrics = Prompt.ask("Metrics: Can you quantify it? (numbers, percentages, etc.)", default="")
    technologies = Prompt.ask("Technologies: What tools/tech did you use?", default="")
    stakeholders = Prompt.ask("Stakeholders: Who was involved/impacted?", default="")
    timeline = Prompt.ask("Timeline: How long did this take?", default="")
    challenges = Prompt.ask("Challenges: What obstacles did you overcome?", default="")
    learning = Prompt.ask("Learning: What did you learn?", default="")

    # Save to database
    acc_id = add_accomplishment(
        conn,
        raw_statement=statement,
        work_experience_id=work_experience_id,
        context=context or None,
        action=action or None,
        result=result or None,
        metrics=metrics or None,
        technologies=technologies or None,
        stakeholders=stakeholders or None,
        timeline=timeline or None,
        challenges=challenges or None,
        learning=learning or None,
    )

    console.print(f"\n[green]✓[/green] Accomplishment #{acc_id} saved.")

    enriched_data = {
        "id": acc_id,
        "statement": statement,
        "context": context,
        "action": action,
        "result": result,
        "metrics": metrics,
        "technologies": technologies,
        "stakeholders": stakeholders,
        "timeline": timeline,
        "challenges": challenges,
        "learning": learning,
    }

    # Generate content from enriched accomplishment
    if generate_content:
        console.print("\n[bold]Generating content from this accomplishment...[/bold]")
        _generate_content_from_accomplishment(console, conn, enriched_data)

    return enriched_data


def _generate_content_from_accomplishment(
    console,
    conn: sqlite3.Connection,
    data: dict,
) -> None:
    """Generate multi-platform content from an enriched accomplishment."""
    from beacon.presence.generator import generate_content_angles

    # Build enriched text
    parts = [f"Accomplishment: {data['statement']}"]
    if data.get("context"):
        parts.append(f"Situation: {data['context']}")
    if data.get("action"):
        parts.append(f"Action: {data['action']}")
    if data.get("result"):
        parts.append(f"Result: {data['result']}")
    if data.get("metrics"):
        parts.append(f"Metrics: {data['metrics']}")
    if data.get("technologies"):
        parts.append(f"Technologies: {data['technologies']}")

    enriched_text = "\n".join(parts)

    try:
        angles = generate_content_angles(enriched_text)
        console.print("\n[bold]Content Angles:[/bold]")
        console.print(angles)

        # Save as draft
        draft_id = add_content_draft(
            conn, "content_angles", "multi", f"Angles: {data['statement'][:50]}",
            angles, metadata={"accomplishment_id": data["id"]},
        )
        console.print(f"\n[dim]Saved as draft #{draft_id}[/dim]")
    except RuntimeError as e:
        console.print(f"[yellow]Content generation skipped: {e}[/yellow]")


def accomplishment_to_content(conn: sqlite3.Connection, acc_id: int) -> dict[str, str] | None:
    """Generate multi-platform content from a stored accomplishment.

    Returns dict with keys: linkedin_post, blog_outline, profile_bullet.
    Returns None if accomplishment not found.
    """
    from beacon.db.content import get_accomplishment_by_id
    from beacon.presence.generator import generate_content_angles

    acc = get_accomplishment_by_id(conn, acc_id)
    if not acc:
        return None

    parts = [f"Accomplishment: {acc['raw_statement']}"]
    for field in ["context", "action", "result", "metrics", "technologies"]:
        if acc[field]:
            parts.append(f"{field.title()}: {acc[field]}")

    enriched_text = "\n".join(parts)

    try:
        angles = generate_content_angles(enriched_text)
        return {"content_angles": angles, "raw_statement": acc["raw_statement"]}
    except RuntimeError:
        return None
