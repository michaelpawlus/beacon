"""Professional profile database operations for Beacon Phase 3."""

import json
import sqlite3


# --- Work Experiences ---

def add_work_experience(
    conn: sqlite3.Connection,
    company: str,
    title: str,
    start_date: str,
    end_date: str | None = None,
    description: str | None = None,
    key_achievements: list[str] | None = None,
    technologies: list[str] | None = None,
    metrics: list[str] | None = None,
) -> int:
    """Add a work experience entry. Returns the new ID."""
    cursor = conn.execute(
        """INSERT INTO work_experiences
           (company, title, start_date, end_date, description,
            key_achievements, technologies, metrics)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (company, title, start_date, end_date, description,
         json.dumps(key_achievements) if key_achievements else None,
         json.dumps(technologies) if technologies else None,
         json.dumps(metrics) if metrics else None),
    )
    conn.commit()
    return cursor.lastrowid


def get_work_experiences(conn: sqlite3.Connection, current_only: bool = False) -> list[sqlite3.Row]:
    """Get work experiences, optionally filtered to current roles only."""
    query = "SELECT * FROM work_experiences"
    if current_only:
        query += " WHERE end_date IS NULL"
    query += " ORDER BY start_date DESC"
    return conn.execute(query).fetchall()


def get_work_experience_by_id(conn: sqlite3.Connection, exp_id: int) -> sqlite3.Row | None:
    """Get a single work experience by ID."""
    return conn.execute("SELECT * FROM work_experiences WHERE id = ?", (exp_id,)).fetchone()


def update_work_experience(conn: sqlite3.Connection, exp_id: int, **kwargs) -> bool:
    """Update a work experience. Returns True if found."""
    if not kwargs:
        return False
    json_fields = {"key_achievements", "technologies", "metrics"}
    sets = []
    params = []
    for key, value in kwargs.items():
        sets.append(f"{key} = ?")
        if key in json_fields and isinstance(value, list):
            params.append(json.dumps(value))
        else:
            params.append(value)
    sets.append("updated_at = datetime('now')")
    params.append(exp_id)
    cursor = conn.execute(
        f"UPDATE work_experiences SET {', '.join(sets)} WHERE id = ?", params,
    )
    conn.commit()
    return cursor.rowcount > 0


def delete_work_experience(conn: sqlite3.Connection, exp_id: int) -> bool:
    """Delete a work experience. Returns True if found."""
    cursor = conn.execute("DELETE FROM work_experiences WHERE id = ?", (exp_id,))
    conn.commit()
    return cursor.rowcount > 0


# --- Projects ---

def add_project(
    conn: sqlite3.Connection,
    name: str,
    description: str | None = None,
    technologies: list[str] | None = None,
    outcomes: list[str] | None = None,
    repo_url: str | None = None,
    is_public: bool = False,
    work_experience_id: int | None = None,
) -> int:
    """Add a project. Returns the new ID."""
    cursor = conn.execute(
        """INSERT INTO projects
           (name, description, technologies, outcomes, repo_url, is_public, work_experience_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (name, description,
         json.dumps(technologies) if technologies else None,
         json.dumps(outcomes) if outcomes else None,
         repo_url, int(is_public), work_experience_id),
    )
    conn.commit()
    return cursor.lastrowid


def get_projects(conn: sqlite3.Connection, work_experience_id: int | None = None) -> list[sqlite3.Row]:
    """Get projects, optionally filtered by work experience."""
    query = "SELECT * FROM projects"
    params: list = []
    if work_experience_id is not None:
        query += " WHERE work_experience_id = ?"
        params.append(work_experience_id)
    query += " ORDER BY created_at DESC"
    return conn.execute(query, params).fetchall()


def get_project_by_id(conn: sqlite3.Connection, project_id: int) -> sqlite3.Row | None:
    """Get a single project by ID."""
    return conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()


def update_project(conn: sqlite3.Connection, project_id: int, **kwargs) -> bool:
    """Update a project. Returns True if found."""
    if not kwargs:
        return False
    json_fields = {"technologies", "outcomes"}
    sets = []
    params = []
    for key, value in kwargs.items():
        sets.append(f"{key} = ?")
        if key in json_fields and isinstance(value, list):
            params.append(json.dumps(value))
        else:
            params.append(value)
    sets.append("updated_at = datetime('now')")
    params.append(project_id)
    cursor = conn.execute(
        f"UPDATE projects SET {', '.join(sets)} WHERE id = ?", params,
    )
    conn.commit()
    return cursor.rowcount > 0


def delete_project(conn: sqlite3.Connection, project_id: int) -> bool:
    """Delete a project. Returns True if found."""
    cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    return cursor.rowcount > 0


# --- Skills ---

def add_skill(
    conn: sqlite3.Connection,
    name: str,
    category: str | None = None,
    proficiency: str | None = None,
    years_experience: int | None = None,
    evidence: list[str] | None = None,
) -> int:
    """Add or upsert a skill (UNIQUE on name). Returns the ID."""
    existing = conn.execute(
        "SELECT id FROM skills WHERE name = ?", (name,)
    ).fetchone()

    if existing:
        # Update existing skill
        sets = ["updated_at = datetime('now')"]
        params: list = []
        if category is not None:
            sets.append("category = ?")
            params.append(category)
        if proficiency is not None:
            sets.append("proficiency = ?")
            params.append(proficiency)
        if years_experience is not None:
            sets.append("years_experience = ?")
            params.append(years_experience)
        if evidence is not None:
            sets.append("evidence = ?")
            params.append(json.dumps(evidence))
        params.append(existing["id"])
        conn.execute(f"UPDATE skills SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
        return existing["id"]
    else:
        cursor = conn.execute(
            """INSERT INTO skills (name, category, proficiency, years_experience, evidence)
               VALUES (?, ?, ?, ?, ?)""",
            (name, category, proficiency, years_experience,
             json.dumps(evidence) if evidence else None),
        )
        conn.commit()
        return cursor.lastrowid


def get_skills(conn: sqlite3.Connection, category: str | None = None) -> list[sqlite3.Row]:
    """Get skills, optionally filtered by category."""
    query = "SELECT * FROM skills"
    params: list = []
    if category:
        query += " WHERE category = ?"
        params.append(category)
    query += " ORDER BY category, name"
    return conn.execute(query, params).fetchall()


def get_skill_by_id(conn: sqlite3.Connection, skill_id: int) -> sqlite3.Row | None:
    """Get a single skill by ID."""
    return conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()


def update_skill(conn: sqlite3.Connection, skill_id: int, **kwargs) -> bool:
    """Update a skill. Returns True if found."""
    if not kwargs:
        return False
    json_fields = {"evidence"}
    sets = []
    params = []
    for key, value in kwargs.items():
        sets.append(f"{key} = ?")
        if key in json_fields and isinstance(value, list):
            params.append(json.dumps(value))
        else:
            params.append(value)
    sets.append("updated_at = datetime('now')")
    params.append(skill_id)
    cursor = conn.execute(
        f"UPDATE skills SET {', '.join(sets)} WHERE id = ?", params,
    )
    conn.commit()
    return cursor.rowcount > 0


def delete_skill(conn: sqlite3.Connection, skill_id: int) -> bool:
    """Delete a skill. Returns True if found."""
    cursor = conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
    conn.commit()
    return cursor.rowcount > 0


# --- Education ---

def add_education(
    conn: sqlite3.Connection,
    institution: str,
    degree: str | None = None,
    field_of_study: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    gpa: float | None = None,
    relevant_coursework: list[str] | None = None,
) -> int:
    """Add an education entry. Returns the new ID."""
    cursor = conn.execute(
        """INSERT INTO education
           (institution, degree, field_of_study, start_date, end_date, gpa, relevant_coursework)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (institution, degree, field_of_study, start_date, end_date, gpa,
         json.dumps(relevant_coursework) if relevant_coursework else None),
    )
    conn.commit()
    return cursor.lastrowid


def get_education(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all education entries."""
    return conn.execute("SELECT * FROM education ORDER BY end_date DESC, start_date DESC").fetchall()


def get_education_by_id(conn: sqlite3.Connection, edu_id: int) -> sqlite3.Row | None:
    """Get a single education entry by ID."""
    return conn.execute("SELECT * FROM education WHERE id = ?", (edu_id,)).fetchone()


def update_education(conn: sqlite3.Connection, edu_id: int, **kwargs) -> bool:
    """Update an education entry. Returns True if found."""
    if not kwargs:
        return False
    json_fields = {"relevant_coursework"}
    sets = []
    params = []
    for key, value in kwargs.items():
        sets.append(f"{key} = ?")
        if key in json_fields and isinstance(value, list):
            params.append(json.dumps(value))
        else:
            params.append(value)
    sets.append("updated_at = datetime('now')")
    params.append(edu_id)
    cursor = conn.execute(
        f"UPDATE education SET {', '.join(sets)} WHERE id = ?", params,
    )
    conn.commit()
    return cursor.rowcount > 0


def delete_education(conn: sqlite3.Connection, edu_id: int) -> bool:
    """Delete an education entry. Returns True if found."""
    cursor = conn.execute("DELETE FROM education WHERE id = ?", (edu_id,))
    conn.commit()
    return cursor.rowcount > 0


# --- Publications & Talks ---

def add_publication(
    conn: sqlite3.Connection,
    title: str,
    pub_type: str,
    venue: str | None = None,
    url: str | None = None,
    date_published: str | None = None,
    description: str | None = None,
) -> int:
    """Add a publication or talk. Returns the new ID."""
    cursor = conn.execute(
        """INSERT INTO publications_talks
           (title, pub_type, venue, url, date_published, description)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, pub_type, venue, url, date_published, description),
    )
    conn.commit()
    return cursor.lastrowid


def get_publications(conn: sqlite3.Connection, pub_type: str | None = None) -> list[sqlite3.Row]:
    """Get publications/talks, optionally filtered by type."""
    query = "SELECT * FROM publications_talks"
    params: list = []
    if pub_type:
        query += " WHERE pub_type = ?"
        params.append(pub_type)
    query += " ORDER BY date_published DESC, created_at DESC"
    return conn.execute(query, params).fetchall()


def get_publication_by_id(conn: sqlite3.Connection, pub_id: int) -> sqlite3.Row | None:
    """Get a single publication by ID."""
    return conn.execute("SELECT * FROM publications_talks WHERE id = ?", (pub_id,)).fetchone()


def update_publication(conn: sqlite3.Connection, pub_id: int, **kwargs) -> bool:
    """Update a publication. Returns True if found."""
    if not kwargs:
        return False
    sets = []
    params = []
    for key, value in kwargs.items():
        sets.append(f"{key} = ?")
        params.append(value)
    sets.append("updated_at = datetime('now')")
    params.append(pub_id)
    cursor = conn.execute(
        f"UPDATE publications_talks SET {', '.join(sets)} WHERE id = ?", params,
    )
    conn.commit()
    return cursor.rowcount > 0


def delete_publication(conn: sqlite3.Connection, pub_id: int) -> bool:
    """Delete a publication. Returns True if found."""
    cursor = conn.execute("DELETE FROM publications_talks WHERE id = ?", (pub_id,))
    conn.commit()
    return cursor.rowcount > 0


# --- Applications ---

def add_application(
    conn: sqlite3.Connection,
    job_id: int,
    status: str = "draft",
    resume_path: str | None = None,
    cover_letter_path: str | None = None,
    applied_date: str | None = None,
    notes: str | None = None,
) -> int:
    """Add an application record. Returns the new ID."""
    cursor = conn.execute(
        """INSERT INTO applications
           (job_id, status, resume_path, cover_letter_path, applied_date, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (job_id, status, resume_path, cover_letter_path, applied_date, notes),
    )
    conn.commit()
    return cursor.lastrowid


def get_applications(
    conn: sqlite3.Connection,
    status: str | None = None,
    job_id: int | None = None,
) -> list[sqlite3.Row]:
    """Get applications with optional filters."""
    query = """SELECT a.*, j.title as job_title, j.url as job_url, c.name as company_name
               FROM applications a
               JOIN job_listings j ON a.job_id = j.id
               JOIN companies c ON j.company_id = c.id
               WHERE 1=1"""
    params: list = []
    if status:
        query += " AND a.status = ?"
        params.append(status)
    if job_id is not None:
        query += " AND a.job_id = ?"
        params.append(job_id)
    query += " ORDER BY a.created_at DESC"
    return conn.execute(query, params).fetchall()


def get_application_by_id(conn: sqlite3.Connection, app_id: int) -> sqlite3.Row | None:
    """Get a single application by ID with job and company info."""
    return conn.execute(
        """SELECT a.*, j.title as job_title, j.url as job_url, c.name as company_name
           FROM applications a
           JOIN job_listings j ON a.job_id = j.id
           JOIN companies c ON j.company_id = c.id
           WHERE a.id = ?""",
        (app_id,),
    ).fetchone()


def update_application(conn: sqlite3.Connection, app_id: int, **kwargs) -> bool:
    """Update an application. Returns True if found."""
    if not kwargs:
        return False
    sets = []
    params = []
    for key, value in kwargs.items():
        sets.append(f"{key} = ?")
        params.append(value)
    sets.append("updated_at = datetime('now')")
    params.append(app_id)
    cursor = conn.execute(
        f"UPDATE applications SET {', '.join(sets)} WHERE id = ?", params,
    )
    conn.commit()
    return cursor.rowcount > 0


def delete_application(conn: sqlite3.Connection, app_id: int) -> bool:
    """Delete an application. Returns True if found."""
    cursor = conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    conn.commit()
    return cursor.rowcount > 0
