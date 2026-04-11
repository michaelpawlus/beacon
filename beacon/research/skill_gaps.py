"""Skill gap analysis — compare user skills against job market demand.

Identifies skills that top job matches require but the user doesn't have,
and highlights strengths where the user's skills align with demand.
"""

import json
import sqlite3

# Aliases that map common variations to a canonical skill name.
# When a job says "JS" or "JavaScript/TypeScript", treat them as the same skill.
SKILL_ALIASES = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "typescript": "JavaScript",
    "javascript/typescript": "JavaScript",
    "js/ts": "JavaScript",
    "node": "Node.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "python": "Python",
    "py": "Python",
    "sql": "SQL",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "docker": "Docker",
    "tf": "Terraform",
    "terraform": "Terraform",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "spark": "Spark",
    "pyspark": "Spark",
    "snowflake": "Snowflake",
    "bigquery": "BigQuery",
    "databricks": "Databricks",
    "dbt": "dbt",
    "airflow": "Airflow",
    "kafka": "Kafka",
    "flink": "Flink",
    "tableau": "Tableau",
    "looker": "Looker",
    "power bi": "Power BI",
    "pandas": "pandas",
    "numpy": "NumPy",
    "scikit-learn": "scikit-learn",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "mlflow": "MLflow",
    "kubeflow": "Kubeflow",
    "sagemaker": "SageMaker",
    "llm": "LLMs",
    "llms": "LLMs",
    "large language model": "LLMs",
    "rag": "RAG",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    "claude": "Claude",
    "openai": "OpenAI",
    "copilot": "GitHub Copilot",
    "github copilot": "GitHub Copilot",
    "cursor": "Cursor",
    "git": "Git",
    "agent": "AI Agents",
    "agentic": "AI Agents",
    "ai agent": "AI Agents",
    "prompt engineering": "Prompt Engineering",
    "prompt design": "Prompt Engineering",
    "embeddings": "Embeddings",
    "vector database": "Vector Databases",
    "vector store": "Vector Databases",
    "fine-tuning": "Fine-tuning",
    "fine tuning": "Fine-tuning",
}

# Categories to assign to newly discovered skills
SKILL_CATEGORIES = {
    "JavaScript": "language", "Python": "language", "SQL": "language",
    "React": "framework", "Node.js": "framework", "Spark": "framework",
    "pandas": "framework", "NumPy": "framework", "scikit-learn": "framework",
    "PyTorch": "framework", "TensorFlow": "framework", "LangChain": "framework",
    "LlamaIndex": "framework",
    "AWS": "tool", "GCP": "tool", "Azure": "tool", "Docker": "tool",
    "Kubernetes": "tool", "Terraform": "tool", "Snowflake": "tool",
    "BigQuery": "tool", "Databricks": "tool", "dbt": "tool",
    "Airflow": "tool", "Kafka": "tool", "Flink": "tool",
    "Tableau": "tool", "Looker": "tool", "Power BI": "tool",
    "MLflow": "tool", "Kubeflow": "tool", "SageMaker": "tool",
    "PostgreSQL": "tool", "Claude": "tool", "OpenAI": "tool",
    "GitHub Copilot": "tool", "Cursor": "tool", "Git": "tool",
    "LLMs": "domain", "RAG": "domain", "AI Agents": "domain",
    "Prompt Engineering": "domain", "Embeddings": "domain",
    "Vector Databases": "domain", "Fine-tuning": "domain",
}


def _normalize_skill(name: str) -> str:
    """Normalize a skill name to its canonical form."""
    return SKILL_ALIASES.get(name.lower().strip(), name.strip())


def _get_user_skills(conn: sqlite3.Connection) -> dict[str, dict]:
    """Load user skills as {canonical_name: {proficiency, years, category}}."""
    rows = conn.execute("SELECT name, category, proficiency, years_experience FROM skills").fetchall()
    skills = {}
    for row in rows:
        canonical = _normalize_skill(row["name"])
        skills[canonical] = {
            "proficiency": row["proficiency"],
            "years": row["years_experience"],
            "category": row["category"],
        }
    return skills


def _get_job_requirements(
    conn: sqlite3.Connection,
    min_relevance: float | None = None,
    location: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Load highlights from top relevant active jobs."""
    from beacon.db.jobs import get_jobs

    rows = get_jobs(conn, status="active", min_relevance=min_relevance, location=location, limit=limit)
    jobs = []
    for row in rows:
        if not row["highlights"]:
            continue
        try:
            hl = json.loads(row["highlights"])
        except (json.JSONDecodeError, TypeError):
            continue

        required_skills = set()
        for tool in hl.get("ai_tools", []):
            required_skills.add(_normalize_skill(tool))
        for req in hl.get("key_requirements", []):
            required_skills.add(_normalize_skill(req))

        if required_skills:
            jobs.append({
                "id": row["id"],
                "title": row["title"],
                "company": row["company_name"],
                "required_skills": required_skills,
            })
    return jobs


def analyze_skill_gaps(
    conn: sqlite3.Connection,
    min_relevance: float | None = None,
    location: str | None = None,
    limit: int = 20,
) -> dict:
    """Analyze skill gaps between user profile and top job matches.

    Returns dict with 'gaps' (skills jobs want but user lacks),
    'strengths' (skills that match), and 'total_jobs_analyzed'.
    """
    user_skills = _get_user_skills(conn)
    jobs = _get_job_requirements(conn, min_relevance=min_relevance, location=location, limit=limit)

    # Count demand for each skill across all analyzed jobs
    skill_demand: dict[str, list[dict]] = {}
    for job in jobs:
        for skill in job["required_skills"]:
            if skill not in skill_demand:
                skill_demand[skill] = []
            skill_demand[skill].append({
                "id": job["id"],
                "title": job["title"],
                "company": job["company"],
            })

    gaps = []
    strengths = []

    for skill, example_jobs in sorted(skill_demand.items(), key=lambda x: len(x[1]), reverse=True):
        entry = {
            "skill": skill,
            "category": SKILL_CATEGORIES.get(skill, "other"),
            "demand_count": len(example_jobs),
            "example_jobs": example_jobs[:3],
        }

        if skill in user_skills:
            entry["proficiency"] = user_skills[skill]["proficiency"]
            entry["years"] = user_skills[skill]["years"]
            strengths.append(entry)
        else:
            entry["proficiency"] = None
            entry["years"] = None
            gaps.append(entry)

    return {
        "gaps": gaps,
        "strengths": strengths,
        "total_jobs_analyzed": len(jobs),
    }


def upsert_skill_gaps(conn: sqlite3.Connection, gaps: list[dict]) -> dict:
    """Persist analyzed gaps to the skill_gaps table. Returns counts."""
    inserted = 0
    updated = 0

    for gap in gaps:
        example_json = json.dumps(gap["example_jobs"])
        existing = conn.execute(
            "SELECT id FROM skill_gaps WHERE skill_name = ?", (gap["skill"],)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE skill_gaps
                   SET demand_count = ?, category = ?, example_jobs = ?,
                       priority = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (gap["demand_count"], gap["category"], example_json,
                 gap["demand_count"], existing["id"]),
            )
            updated += 1
        else:
            conn.execute(
                """INSERT INTO skill_gaps (skill_name, category, demand_count, example_jobs, priority)
                   VALUES (?, ?, ?, ?, ?)""",
                (gap["skill"], gap["category"], gap["demand_count"],
                 example_json, gap["demand_count"]),
            )
            inserted += 1

    conn.commit()
    return {"inserted": inserted, "updated": updated}


def get_skill_gaps(
    conn: sqlite3.Connection,
    status: str | None = None,
) -> list[sqlite3.Row]:
    """Get skill gaps, optionally filtered by status."""
    query = "SELECT * FROM skill_gaps WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY demand_count DESC, skill_name"
    return conn.execute(query, params).fetchall()


def update_skill_gap_status(conn: sqlite3.Connection, skill_name: str, status: str) -> bool:
    """Update a skill gap's status. Returns True if found."""
    cursor = conn.execute(
        "UPDATE skill_gaps SET status = ?, updated_at = datetime('now') WHERE skill_name = ?",
        (status, skill_name),
    )
    conn.commit()
    return cursor.rowcount > 0


def export_gaps_as_quests(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """Export open skill gaps as quest-ready dicts for code-daily."""
    rows = get_skill_gaps(conn, status="open")
    quests = []
    for row in rows[:limit]:
        examples = []
        if row["example_jobs"]:
            try:
                examples = json.loads(row["example_jobs"])
            except (json.JSONDecodeError, TypeError):
                pass
        example_text = ", ".join(f"{j['company']} - {j['title']}" for j in examples[:2])

        quests.append({
            "title": f"[beacon-gap] Learn {row['skill_name']} ({row['demand_count']} jobs require it)",
            "source": "beacon_gap",
            "source_ref": f"beacon_gap:{row['skill_name'].lower().replace(' ', '_')}",
            "description": (
                f"Skill gap: {row['demand_count']} of your top job matches require {row['skill_name']}. "
                f"Example: {example_text}." if example_text else
                f"Skill gap: {row['demand_count']} of your top job matches require {row['skill_name']}."
            ),
            "skill_name": row["skill_name"],
            "demand_count": row["demand_count"],
        })
    return quests
