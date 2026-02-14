"""Interactive profile interview tool for Beacon Phase 3.

Walks users through a structured questionnaire to populate the professional
profile knowledge base using Rich prompts.
"""

import re

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from beacon.db.profile import (
    add_education,
    add_project,
    add_publication,
    add_skill,
    add_work_experience,
    get_work_experiences,
)


def _validate_date(date_str: str) -> bool:
    """Validate a date string as YYYY-MM or YYYY-MM-DD."""
    return bool(re.match(r"^\d{4}-\d{2}(-\d{2})?$", date_str))


def _collect_list_input(console: Console, prompt_text: str = "Enter items (one per line, empty line to finish)") -> list[str]:
    """Collect multi-line input for bullet point lists."""
    console.print(f"  [dim]{prompt_text}[/dim]")
    items = []
    while True:
        line = Prompt.ask("  ", default="")
        if not line:
            break
        items.append(line)
    return items


def interview_work_experience(console: Console, conn) -> int | None:
    """Interview for a single work experience entry."""
    console.print(Panel("[bold]Work Experience[/bold]", style="blue"))

    company = Prompt.ask("Company name")
    if not company:
        return None

    title = Prompt.ask("Job title")
    start_date = Prompt.ask("Start date (YYYY-MM)")
    while not _validate_date(start_date):
        console.print("  [red]Invalid date format. Use YYYY-MM or YYYY-MM-DD.[/red]")
        start_date = Prompt.ask("Start date (YYYY-MM)")

    is_current = Confirm.ask("Is this your current role?", default=False)
    end_date = None
    if not is_current:
        end_date = Prompt.ask("End date (YYYY-MM)")
        while not _validate_date(end_date):
            console.print("  [red]Invalid date format. Use YYYY-MM or YYYY-MM-DD.[/red]")
            end_date = Prompt.ask("End date (YYYY-MM)")

    description = Prompt.ask("Brief description", default="")

    console.print("\n[bold]Key achievements:[/bold]")
    achievements = _collect_list_input(console, "Enter achievements (one per line, empty line to finish)")

    console.print("\n[bold]Technologies used:[/bold]")
    technologies = _collect_list_input(console, "Enter technologies (one per line, empty line to finish)")

    console.print("\n[bold]Quantified metrics:[/bold]")
    metrics = _collect_list_input(console, "Enter metrics (one per line, empty line to finish)")

    exp_id = add_work_experience(
        conn, company, title, start_date,
        end_date=end_date,
        description=description or None,
        key_achievements=achievements or None,
        technologies=technologies or None,
        metrics=metrics or None,
    )
    console.print(f"  [green]✓[/green] Added work experience at {company}")
    return exp_id


def interview_project(console: Console, conn) -> int | None:
    """Interview for a single project entry."""
    console.print(Panel("[bold]Project[/bold]", style="blue"))

    name = Prompt.ask("Project name")
    if not name:
        return None

    description = Prompt.ask("Description", default="")

    console.print("\n[bold]Technologies used:[/bold]")
    technologies = _collect_list_input(console, "Enter technologies (one per line, empty line to finish)")

    console.print("\n[bold]Outcomes/results:[/bold]")
    outcomes = _collect_list_input(console, "Enter outcomes (one per line, empty line to finish)")

    repo_url = Prompt.ask("Repository URL (optional)", default="")
    is_public = Confirm.ask("Is this project public?", default=False)

    # Optionally link to work experience
    work_experience_id = None
    work_exps = get_work_experiences(conn)
    if work_exps and Confirm.ask("Link to a work experience?", default=False):
        console.print("  Available work experiences:")
        for exp in work_exps:
            console.print(f"    [{exp['id']}] {exp['company']} — {exp['title']}")
        exp_id_str = Prompt.ask("Work experience ID")
        try:
            work_experience_id = int(exp_id_str)
        except ValueError:
            pass

    pid = add_project(
        conn, name,
        description=description or None,
        technologies=technologies or None,
        outcomes=outcomes or None,
        repo_url=repo_url or None,
        is_public=is_public,
        work_experience_id=work_experience_id,
    )
    console.print(f"  [green]✓[/green] Added project: {name}")
    return pid


def interview_skill(console: Console, conn) -> int | None:
    """Interview for a single skill entry."""
    console.print(Panel("[bold]Skill[/bold]", style="blue"))

    name = Prompt.ask("Skill name")
    if not name:
        return None

    category = Prompt.ask("Category (language/framework/tool/domain/other)", default="")
    proficiency = Prompt.ask("Proficiency (beginner/intermediate/advanced/expert)", default="")
    years_str = Prompt.ask("Years of experience", default="")
    years = int(years_str) if years_str.isdigit() else None

    console.print("\n[bold]Evidence:[/bold]")
    evidence = _collect_list_input(console, "Enter evidence (one per line, empty line to finish)")

    sid = add_skill(
        conn, name,
        category=category or None,
        proficiency=proficiency or None,
        years_experience=years,
        evidence=evidence or None,
    )
    console.print(f"  [green]✓[/green] Added skill: {name}")
    return sid


def interview_education(console: Console, conn) -> int | None:
    """Interview for a single education entry."""
    console.print(Panel("[bold]Education[/bold]", style="blue"))

    institution = Prompt.ask("Institution")
    if not institution:
        return None

    degree = Prompt.ask("Degree (e.g., BS, MS, PhD)", default="")
    field = Prompt.ask("Field of study", default="")
    start_date = Prompt.ask("Start date (YYYY-MM, optional)", default="")
    end_date = Prompt.ask("End date (YYYY-MM, optional)", default="")
    gpa_str = Prompt.ask("GPA (optional)", default="")
    gpa = float(gpa_str) if gpa_str else None

    console.print("\n[bold]Relevant coursework:[/bold]")
    coursework = _collect_list_input(console, "Enter courses (one per line, empty line to finish)")

    eid = add_education(
        conn, institution,
        degree=degree or None,
        field_of_study=field or None,
        start_date=start_date or None,
        end_date=end_date or None,
        gpa=gpa,
        relevant_coursework=coursework or None,
    )
    console.print(f"  [green]✓[/green] Added education: {institution}")
    return eid


def interview_publication(console: Console, conn) -> int | None:
    """Interview for a single publication/talk entry."""
    console.print(Panel("[bold]Publication / Talk[/bold]", style="blue"))

    title = Prompt.ask("Title")
    if not title:
        return None

    pub_type = Prompt.ask(
        "Type (blog_post/paper/talk/panel/podcast/workshop/open_source)",
        default="blog_post",
    )
    venue = Prompt.ask("Venue/publication (optional)", default="")
    url = Prompt.ask("URL (optional)", default="")
    date_published = Prompt.ask("Date published (YYYY-MM, optional)", default="")
    description = Prompt.ask("Brief description (optional)", default="")

    pid = add_publication(
        conn, title, pub_type,
        venue=venue or None,
        url=url or None,
        date_published=date_published or None,
        description=description or None,
    )
    console.print(f"  [green]✓[/green] Added: {title}")
    return pid


SECTION_LABELS = {
    "work": "Work Experience",
    "projects": "Projects",
    "skills": "Skills",
    "education": "Education",
    "publications": "Publications & Talks",
}

SECTION_FUNCTIONS = {
    "work": "interview_work_experience",
    "projects": "interview_project",
    "skills": "interview_skill",
    "education": "interview_education",
    "publications": "interview_publication",
}


def run_full_interview(console: Console, conn, section: str | None = None) -> dict:
    """Run the full profile interview or a single section.

    Returns a dict with counts per category.
    """
    import beacon.interview as _self

    counts = {}

    if section:
        keys = [section]
    else:
        keys = list(SECTION_FUNCTIONS.keys())

    for key in keys:
        label = SECTION_LABELS[key]
        func = getattr(_self, SECTION_FUNCTIONS[key])
        console.print(f"\n[bold cyan]━━━ {label} ━━━[/bold cyan]\n")
        count = 0
        while True:
            result = func(console, conn)
            if result is not None:
                count += 1
            if not Confirm.ask(f"\nAdd another {label.lower()} entry?", default=False):
                break
        counts[key] = count

    console.print(Panel("[bold green]Interview complete![/bold green]", style="green"))
    for key, count in counts.items():
        console.print(f"  {SECTION_LABELS[key]}: {count} entries added")

    return counts
