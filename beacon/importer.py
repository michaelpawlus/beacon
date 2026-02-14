"""Profile import/export utility for Beacon Phase 3.

Supports bulk import from JSON files and full profile export for backup.
"""

import json
import sqlite3
from pathlib import Path

from beacon.db.profile import (
    add_education,
    add_project,
    add_publication,
    add_skill,
    add_work_experience,
    get_education,
    get_projects,
    get_publications,
    get_skills,
    get_work_experiences,
)


VALID_PUB_TYPES = {"blog_post", "paper", "talk", "panel", "podcast", "workshop", "open_source"}
VALID_PROFICIENCIES = {"beginner", "intermediate", "advanced", "expert"}


def _validate_work_experience(data: dict) -> list[str]:
    """Validate a work experience entry. Returns list of errors."""
    errors = []
    if not data.get("company"):
        errors.append("company is required")
    if not data.get("title"):
        errors.append("title is required")
    if not data.get("start_date"):
        errors.append("start_date is required")
    return errors


def _validate_project(data: dict) -> list[str]:
    """Validate a project entry. Returns list of errors."""
    errors = []
    if not data.get("name"):
        errors.append("name is required")
    return errors


def _validate_skill(data: dict) -> list[str]:
    """Validate a skill entry. Returns list of errors."""
    errors = []
    if not data.get("name"):
        errors.append("name is required")
    if data.get("proficiency") and data["proficiency"] not in VALID_PROFICIENCIES:
        errors.append(f"proficiency must be one of: {', '.join(VALID_PROFICIENCIES)}")
    return errors


def _validate_education(data: dict) -> list[str]:
    """Validate an education entry. Returns list of errors."""
    errors = []
    if not data.get("institution"):
        errors.append("institution is required")
    return errors


def _validate_publication(data: dict) -> list[str]:
    """Validate a publication entry. Returns list of errors."""
    errors = []
    if not data.get("title"):
        errors.append("title is required")
    if not data.get("pub_type"):
        errors.append("pub_type is required")
    elif data["pub_type"] not in VALID_PUB_TYPES:
        errors.append(f"pub_type must be one of: {', '.join(VALID_PUB_TYPES)}")
    return errors


def _import_json(conn: sqlite3.Connection, path: Path) -> dict:
    """Import profile data from a JSON file."""
    data = json.loads(path.read_text())
    counts = {}
    errors = []

    # Work experiences
    for i, item in enumerate(data.get("work_experiences", [])):
        item_errors = _validate_work_experience(item)
        if item_errors:
            errors.extend([f"work_experiences[{i}]: {e}" for e in item_errors])
            continue
        add_work_experience(
            conn, item["company"], item["title"], item["start_date"],
            end_date=item.get("end_date"),
            description=item.get("description"),
            key_achievements=item.get("key_achievements"),
            technologies=item.get("technologies"),
            metrics=item.get("metrics"),
        )
    counts["work_experiences"] = len(data.get("work_experiences", []))

    # Projects
    for i, item in enumerate(data.get("projects", [])):
        item_errors = _validate_project(item)
        if item_errors:
            errors.extend([f"projects[{i}]: {e}" for e in item_errors])
            continue
        add_project(
            conn, item["name"],
            description=item.get("description"),
            technologies=item.get("technologies"),
            outcomes=item.get("outcomes"),
            repo_url=item.get("repo_url"),
            is_public=item.get("is_public", False),
        )
    counts["projects"] = len(data.get("projects", []))

    # Skills
    for i, item in enumerate(data.get("skills", [])):
        item_errors = _validate_skill(item)
        if item_errors:
            errors.extend([f"skills[{i}]: {e}" for e in item_errors])
            continue
        add_skill(
            conn, item["name"],
            category=item.get("category"),
            proficiency=item.get("proficiency"),
            years_experience=item.get("years_experience"),
            evidence=item.get("evidence"),
        )
    counts["skills"] = len(data.get("skills", []))

    # Education
    for i, item in enumerate(data.get("education", [])):
        item_errors = _validate_education(item)
        if item_errors:
            errors.extend([f"education[{i}]: {e}" for e in item_errors])
            continue
        add_education(
            conn, item["institution"],
            degree=item.get("degree"),
            field_of_study=item.get("field_of_study"),
            start_date=item.get("start_date"),
            end_date=item.get("end_date"),
            gpa=item.get("gpa"),
            relevant_coursework=item.get("relevant_coursework"),
        )
    counts["education"] = len(data.get("education", []))

    # Publications & Talks
    for i, item in enumerate(data.get("publications_talks", [])):
        item_errors = _validate_publication(item)
        if item_errors:
            errors.extend([f"publications_talks[{i}]: {e}" for e in item_errors])
            continue
        add_publication(
            conn, item["title"], item["pub_type"],
            venue=item.get("venue"),
            url=item.get("url"),
            date_published=item.get("date_published"),
            description=item.get("description"),
        )
    counts["publications_talks"] = len(data.get("publications_talks", []))

    if errors:
        counts["errors"] = errors

    return counts


def import_profile(conn: sqlite3.Connection, file_path: str | Path) -> dict:
    """Import profile data from a file. Returns counts per section."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix == ".json":
        return _import_json(conn, path)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}. Use .json")


def export_profile_json(conn: sqlite3.Connection) -> str:
    """Export full profile as JSON string for backup/transfer."""
    profile = {}

    # Work experiences
    work_exps = get_work_experiences(conn)
    profile["work_experiences"] = []
    for exp in work_exps:
        entry = {
            "company": exp["company"],
            "title": exp["title"],
            "start_date": exp["start_date"],
            "end_date": exp["end_date"],
            "description": exp["description"],
        }
        if exp["key_achievements"]:
            entry["key_achievements"] = json.loads(exp["key_achievements"])
        if exp["technologies"]:
            entry["technologies"] = json.loads(exp["technologies"])
        if exp["metrics"]:
            entry["metrics"] = json.loads(exp["metrics"])
        profile["work_experiences"].append(entry)

    # Projects
    projects = get_projects(conn)
    profile["projects"] = []
    for proj in projects:
        entry = {
            "name": proj["name"],
            "description": proj["description"],
            "repo_url": proj["repo_url"],
            "is_public": bool(proj["is_public"]),
        }
        if proj["technologies"]:
            entry["technologies"] = json.loads(proj["technologies"])
        if proj["outcomes"]:
            entry["outcomes"] = json.loads(proj["outcomes"])
        profile["projects"].append(entry)

    # Skills
    skills = get_skills(conn)
    profile["skills"] = []
    for skill in skills:
        entry = {
            "name": skill["name"],
            "category": skill["category"],
            "proficiency": skill["proficiency"],
            "years_experience": skill["years_experience"],
        }
        if skill["evidence"]:
            entry["evidence"] = json.loads(skill["evidence"])
        profile["skills"].append(entry)

    # Education
    edu_list = get_education(conn)
    profile["education"] = []
    for edu in edu_list:
        entry = {
            "institution": edu["institution"],
            "degree": edu["degree"],
            "field_of_study": edu["field_of_study"],
            "start_date": edu["start_date"],
            "end_date": edu["end_date"],
            "gpa": edu["gpa"],
        }
        if edu["relevant_coursework"]:
            entry["relevant_coursework"] = json.loads(edu["relevant_coursework"])
        profile["education"].append(entry)

    # Publications & Talks
    pubs = get_publications(conn)
    profile["publications_talks"] = []
    for pub in pubs:
        entry = {
            "title": pub["title"],
            "pub_type": pub["pub_type"],
            "venue": pub["venue"],
            "url": pub["url"],
            "date_published": pub["date_published"],
            "description": pub["description"],
        }
        profile["publications_talks"].append(entry)

    return json.dumps(profile, indent=2)
