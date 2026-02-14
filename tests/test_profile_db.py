"""Tests for professional profile database operations."""

import json

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.db.profile import (
    add_application,
    add_education,
    add_project,
    add_publication,
    add_skill,
    add_work_experience,
    delete_application,
    delete_education,
    delete_project,
    delete_publication,
    delete_skill,
    delete_work_experience,
    get_applications,
    get_application_by_id,
    get_education,
    get_education_by_id,
    get_project_by_id,
    get_projects,
    get_publication_by_id,
    get_publications,
    get_skill_by_id,
    get_skills,
    get_work_experience_by_id,
    get_work_experiences,
    update_application,
    update_education,
    update_project,
    update_publication,
    update_skill,
    update_work_experience,
)
from beacon.db.jobs import upsert_job


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _insert_company(conn, name="TestCo"):
    conn.execute(
        "INSERT INTO companies (name, remote_policy, size_bucket) VALUES (?, 'hybrid', 'mid-200-1000')",
        (name,),
    )
    conn.commit()
    return conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()["id"]


# --- Work Experiences ---

class TestWorkExperiences:
    def test_add_work_experience(self, db):
        exp_id = add_work_experience(db, "Acme Corp", "Data Engineer", "2022-01")
        assert exp_id > 0

    def test_add_with_all_fields(self, db):
        exp_id = add_work_experience(
            db, "Acme Corp", "Senior Data Engineer", "2022-01", end_date="2024-06",
            description="Built data pipelines",
            key_achievements=["Reduced latency by 50%", "Led team of 3"],
            technologies=["Python", "Spark", "dbt"],
            metrics=["50% latency reduction", "3x throughput"],
        )
        row = get_work_experience_by_id(db, exp_id)
        assert row["company"] == "Acme Corp"
        assert json.loads(row["key_achievements"]) == ["Reduced latency by 50%", "Led team of 3"]
        assert json.loads(row["technologies"]) == ["Python", "Spark", "dbt"]

    def test_get_work_experiences_all(self, db):
        add_work_experience(db, "Co A", "Engineer", "2020-01", end_date="2022-01")
        add_work_experience(db, "Co B", "Senior Engineer", "2022-01")
        exps = get_work_experiences(db)
        assert len(exps) == 2

    def test_get_work_experiences_current_only(self, db):
        add_work_experience(db, "Co A", "Engineer", "2020-01", end_date="2022-01")
        add_work_experience(db, "Co B", "Senior Engineer", "2022-01")
        exps = get_work_experiences(db, current_only=True)
        assert len(exps) == 1
        assert exps[0]["company"] == "Co B"

    def test_update_work_experience(self, db):
        exp_id = add_work_experience(db, "Acme", "Engineer", "2022-01")
        assert update_work_experience(db, exp_id, title="Senior Engineer") is True
        row = get_work_experience_by_id(db, exp_id)
        assert row["title"] == "Senior Engineer"

    def test_update_json_field(self, db):
        exp_id = add_work_experience(db, "Acme", "Engineer", "2022-01")
        assert update_work_experience(db, exp_id, technologies=["Python", "SQL"]) is True
        row = get_work_experience_by_id(db, exp_id)
        assert json.loads(row["technologies"]) == ["Python", "SQL"]

    def test_update_nonexistent_returns_false(self, db):
        assert update_work_experience(db, 99999, title="X") is False

    def test_update_empty_kwargs_returns_false(self, db):
        exp_id = add_work_experience(db, "Acme", "Engineer", "2022-01")
        assert update_work_experience(db, exp_id) is False

    def test_delete_work_experience(self, db):
        exp_id = add_work_experience(db, "Acme", "Engineer", "2022-01")
        assert delete_work_experience(db, exp_id) is True
        assert get_work_experience_by_id(db, exp_id) is None

    def test_delete_nonexistent_returns_false(self, db):
        assert delete_work_experience(db, 99999) is False


# --- Projects ---

class TestProjects:
    def test_add_project(self, db):
        pid = add_project(db, "Beacon", description="Job search tool")
        assert pid > 0

    def test_add_project_with_work_experience(self, db):
        exp_id = add_work_experience(db, "Acme", "Engineer", "2022-01")
        pid = add_project(db, "Pipeline", work_experience_id=exp_id,
                          technologies=["Python", "Airflow"],
                          outcomes=["Automated 100 reports"])
        row = get_project_by_id(db, pid)
        assert row["work_experience_id"] == exp_id
        assert json.loads(row["technologies"]) == ["Python", "Airflow"]

    def test_get_projects_all(self, db):
        add_project(db, "Project A")
        add_project(db, "Project B")
        projects = get_projects(db)
        assert len(projects) == 2

    def test_get_projects_by_work_experience(self, db):
        exp_id = add_work_experience(db, "Acme", "Engineer", "2022-01")
        add_project(db, "Work Project", work_experience_id=exp_id)
        add_project(db, "Personal Project")
        projects = get_projects(db, work_experience_id=exp_id)
        assert len(projects) == 1
        assert projects[0]["name"] == "Work Project"

    def test_update_project(self, db):
        pid = add_project(db, "Old Name")
        assert update_project(db, pid, name="New Name") is True
        assert get_project_by_id(db, pid)["name"] == "New Name"

    def test_delete_project(self, db):
        pid = add_project(db, "Temp")
        assert delete_project(db, pid) is True
        assert get_project_by_id(db, pid) is None

    def test_fk_cascade_sets_null_on_work_exp_delete(self, db):
        exp_id = add_work_experience(db, "Acme", "Engineer", "2022-01")
        pid = add_project(db, "Pipeline", work_experience_id=exp_id)
        delete_work_experience(db, exp_id)
        row = get_project_by_id(db, pid)
        assert row is not None
        assert row["work_experience_id"] is None


# --- Skills ---

class TestSkills:
    def test_add_skill(self, db):
        sid = add_skill(db, "Python", category="language", proficiency="expert", years_experience=10)
        assert sid > 0

    def test_upsert_skill_updates_existing(self, db):
        sid1 = add_skill(db, "Python", proficiency="intermediate")
        sid2 = add_skill(db, "Python", proficiency="expert")
        assert sid1 == sid2
        row = get_skill_by_id(db, sid1)
        assert row["proficiency"] == "expert"

    def test_upsert_preserves_unspecified_fields(self, db):
        add_skill(db, "Python", category="language", proficiency="expert")
        add_skill(db, "Python", years_experience=10)
        skills = get_skills(db)
        assert len(skills) == 1
        assert skills[0]["category"] == "language"

    def test_get_skills_by_category(self, db):
        add_skill(db, "Python", category="language")
        add_skill(db, "SQL", category="language")
        add_skill(db, "dbt", category="tool")
        langs = get_skills(db, category="language")
        assert len(langs) == 2

    def test_update_skill(self, db):
        sid = add_skill(db, "Python")
        assert update_skill(db, sid, proficiency="expert") is True

    def test_delete_skill(self, db):
        sid = add_skill(db, "Python")
        assert delete_skill(db, sid) is True
        assert get_skill_by_id(db, sid) is None

    def test_skill_evidence_json(self, db):
        sid = add_skill(db, "Python", evidence=["Built pipeline", "Open source contrib"])
        row = get_skill_by_id(db, sid)
        assert json.loads(row["evidence"]) == ["Built pipeline", "Open source contrib"]


# --- Education ---

class TestEducation:
    def test_add_education(self, db):
        eid = add_education(db, "MIT", degree="MS", field_of_study="Computer Science")
        assert eid > 0

    def test_add_education_with_coursework(self, db):
        eid = add_education(db, "Stanford", relevant_coursework=["ML", "Databases", "Stats"])
        row = get_education_by_id(db, eid)
        assert json.loads(row["relevant_coursework"]) == ["ML", "Databases", "Stats"]

    def test_get_education(self, db):
        add_education(db, "MIT")
        add_education(db, "Stanford")
        assert len(get_education(db)) == 2

    def test_update_education(self, db):
        eid = add_education(db, "MIT")
        assert update_education(db, eid, degree="PhD") is True
        assert get_education_by_id(db, eid)["degree"] == "PhD"

    def test_delete_education(self, db):
        eid = add_education(db, "MIT")
        assert delete_education(db, eid) is True
        assert get_education_by_id(db, eid) is None


# --- Publications & Talks ---

class TestPublications:
    def test_add_publication(self, db):
        pid = add_publication(db, "My Talk", "talk", venue="PyCon")
        assert pid > 0

    def test_add_publication_all_types(self, db):
        for pub_type in ["blog_post", "paper", "talk", "panel", "podcast", "workshop", "open_source"]:
            pid = add_publication(db, f"Test {pub_type}", pub_type)
            assert pid > 0

    def test_get_publications_by_type(self, db):
        add_publication(db, "Blog 1", "blog_post")
        add_publication(db, "Talk 1", "talk")
        add_publication(db, "Blog 2", "blog_post")
        blogs = get_publications(db, pub_type="blog_post")
        assert len(blogs) == 2

    def test_update_publication(self, db):
        pid = add_publication(db, "Draft", "blog_post")
        assert update_publication(db, pid, title="Final Title") is True
        assert get_publication_by_id(db, pid)["title"] == "Final Title"

    def test_delete_publication(self, db):
        pid = add_publication(db, "Temp", "blog_post")
        assert delete_publication(db, pid) is True
        assert get_publication_by_id(db, pid) is None

    def test_invalid_pub_type_raises(self, db):
        with pytest.raises(Exception):
            add_publication(db, "Bad", "invalid_type")


# --- Applications ---

class TestApplications:
    def test_add_application(self, db):
        cid = _insert_company(db)
        result = upsert_job(db, cid, "Data Engineer", url="https://x.com/1")
        app_id = add_application(db, result["id"])
        assert app_id > 0

    def test_get_applications(self, db):
        cid = _insert_company(db)
        r1 = upsert_job(db, cid, "Job A", url="https://x.com/a")
        r2 = upsert_job(db, cid, "Job B", url="https://x.com/b")
        add_application(db, r1["id"], status="applied")
        add_application(db, r2["id"], status="draft")
        apps = get_applications(db)
        assert len(apps) == 2
        assert apps[0]["company_name"] == "TestCo"

    def test_filter_by_status(self, db):
        cid = _insert_company(db)
        r1 = upsert_job(db, cid, "Job A", url="https://x.com/a")
        r2 = upsert_job(db, cid, "Job B", url="https://x.com/b")
        add_application(db, r1["id"], status="applied")
        add_application(db, r2["id"], status="draft")
        apps = get_applications(db, status="applied")
        assert len(apps) == 1

    def test_update_application_status(self, db):
        cid = _insert_company(db)
        r = upsert_job(db, cid, "Job", url="https://x.com/1")
        app_id = add_application(db, r["id"])
        assert update_application(db, app_id, status="interview") is True
        app = get_application_by_id(db, app_id)
        assert app["status"] == "interview"

    def test_delete_application(self, db):
        cid = _insert_company(db)
        r = upsert_job(db, cid, "Job", url="https://x.com/1")
        app_id = add_application(db, r["id"])
        assert delete_application(db, app_id) is True
        assert get_application_by_id(db, app_id) is None

    def test_fk_cascade_on_job_delete(self, db):
        cid = _insert_company(db)
        r = upsert_job(db, cid, "Job", url="https://x.com/1")
        app_id = add_application(db, r["id"])
        db.execute("DELETE FROM job_listings WHERE id = ?", (r["id"],))
        db.commit()
        assert get_application_by_id(db, app_id) is None

    def test_application_with_paths(self, db):
        cid = _insert_company(db)
        r = upsert_job(db, cid, "Job", url="https://x.com/1")
        app_id = add_application(db, r["id"], resume_path="/tmp/resume.pdf",
                                  cover_letter_path="/tmp/cover.pdf",
                                  notes="Referred by John")
        app = get_application_by_id(db, app_id)
        assert app["resume_path"] == "/tmp/resume.pdf"
        assert app["notes"] == "Referred by John"


# --- Schema Integrity ---

class TestSchemaIntegrity:
    def test_all_phase3_tables_exist(self, db):
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        for expected in ["work_experiences", "projects", "skills", "education", "publications_talks", "applications"]:
            assert expected in table_names, f"Table {expected} missing"

    def test_skills_unique_constraint(self, db):
        db.execute("INSERT INTO skills (name, category) VALUES ('Python', 'language')")
        db.commit()
        with pytest.raises(Exception):
            db.execute("INSERT INTO skills (name, category) VALUES ('Python', 'tool')")
            db.commit()

    def test_publication_type_check_constraint(self, db):
        with pytest.raises(Exception):
            db.execute("INSERT INTO publications_talks (title, pub_type) VALUES ('X', 'invalid')")
            db.commit()

    def test_application_status_check_constraint(self, db):
        cid = _insert_company(db)
        r = upsert_job(db, cid, "Job", url="https://x.com/1")
        with pytest.raises(Exception):
            db.execute("INSERT INTO applications (job_id, status) VALUES (?, 'invalid')", (r["id"],))
            db.commit()

    def test_proficiency_check_constraint(self, db):
        with pytest.raises(Exception):
            db.execute("INSERT INTO skills (name, proficiency) VALUES ('X', 'godlike')")
            db.commit()
