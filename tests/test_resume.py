"""Tests for resume tailoring engine."""

import json
from unittest.mock import MagicMock, patch

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.db.jobs import upsert_job
from beacon.db.profile import (
    add_education,
    add_project,
    add_skill,
    add_work_experience,
)
from beacon.llm.client import LLMResponse
from beacon.materials.resume import (
    TailoredResume,
    _format_profile_for_prompt,
    select_relevant_items,
    tailor_resume,
)
from beacon.materials.renderer import render_markdown


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


def _populate_profile(conn):
    """Add sample profile data for testing."""
    add_work_experience(conn, "DataCo", "Senior Data Engineer", "2022-01",
                        description="Built data pipelines",
                        technologies=["Python", "Spark", "dbt", "SQL"],
                        key_achievements=["Reduced latency by 50%", "Led team of 3"],
                        metrics=["50% latency reduction"])
    add_work_experience(conn, "StartupInc", "Data Analyst", "2019-06", end_date="2021-12",
                        technologies=["Python", "SQL", "Tableau"])
    add_project(conn, "Beacon", description="Job search intelligence tool",
                technologies=["Python", "SQLite", "Rich"])
    add_skill(conn, "Python", category="language", proficiency="expert", years_experience=10)
    add_skill(conn, "SQL", category="language", proficiency="advanced")
    add_skill(conn, "Spark", category="framework", proficiency="advanced")
    add_skill(conn, "dbt", category="tool", proficiency="advanced")
    add_skill(conn, "JavaScript", category="language", proficiency="intermediate")
    add_education(conn, "State University", degree="BS", field_of_study="Computer Science")


class TestSelectRelevantItems:
    def test_selects_relevant_skills(self, db):
        _populate_profile(db)
        requirements = {
            "required_skills": ["Python", "SQL", "Spark"],
            "preferred_skills": ["dbt"],
            "keywords": ["data engineering"],
        }
        result = select_relevant_items(db, requirements)
        skill_names = [s["name"] for s in result["skills"]]
        assert "Python" in skill_names
        assert "SQL" in skill_names
        assert "Spark" in skill_names

    def test_includes_all_work_experiences(self, db):
        _populate_profile(db)
        requirements = {"required_skills": ["Python"], "preferred_skills": [], "keywords": []}
        result = select_relevant_items(db, requirements)
        assert len(result["work_experiences"]) == 2

    def test_sorts_work_by_relevance(self, db):
        _populate_profile(db)
        requirements = {
            "required_skills": ["Spark", "dbt"],
            "preferred_skills": [],
            "keywords": [],
        }
        result = select_relevant_items(db, requirements)
        # DataCo has Spark and dbt, should be first
        assert result["work_experiences"][0]["company"] == "DataCo"

    def test_limits_projects(self, db):
        for i in range(10):
            add_project(db, f"Project {i}")
        requirements = {"required_skills": [], "preferred_skills": [], "keywords": []}
        result = select_relevant_items(db, requirements)
        assert len(result["projects"]) <= 5

    def test_empty_profile(self, db):
        requirements = {"required_skills": ["Python"], "preferred_skills": [], "keywords": []}
        result = select_relevant_items(db, requirements)
        assert result["work_experiences"] == []
        assert result["skills"] == []


class TestFormatProfile:
    def test_formats_work_experience(self, db):
        _populate_profile(db)
        requirements = {"required_skills": ["Python"], "preferred_skills": [], "keywords": []}
        profile_data = select_relevant_items(db, requirements)
        text = _format_profile_for_prompt(profile_data)
        assert "DataCo" in text
        assert "Senior Data Engineer" in text
        assert "Python" in text

    def test_formats_skills(self, db):
        _populate_profile(db)
        requirements = {"required_skills": ["Python"], "preferred_skills": [], "keywords": []}
        profile_data = select_relevant_items(db, requirements)
        text = _format_profile_for_prompt(profile_data)
        assert "## Skills" in text

    def test_formats_education(self, db):
        _populate_profile(db)
        requirements = {"required_skills": [], "preferred_skills": [], "keywords": []}
        profile_data = select_relevant_items(db, requirements)
        text = _format_profile_for_prompt(profile_data)
        assert "State University" in text


class TestTailorResume:
    @patch("beacon.materials.resume.generate")
    @patch("beacon.materials.resume.generate_structured")
    def test_tailor_resume_pipeline(self, mock_structured, mock_generate, db):
        cid = _insert_company(db)
        job = upsert_job(db, cid, "Data Engineer", url="https://x.com/1",
                         description_text="Looking for Python, SQL, Spark expert")
        _populate_profile(db)

        mock_structured.return_value = {
            "required_skills": ["Python", "SQL", "Spark"],
            "preferred_skills": ["dbt"],
            "seniority": "senior",
            "keywords": ["data engineering", "pipeline"],
            "responsibilities": ["Build data pipelines"],
            "culture_signals": [],
        }
        mock_generate.return_value = LLMResponse(
            text="# Resume\n## Summary\nExperienced data engineer...",
            model="claude-sonnet-4-5-20250929",
            input_tokens=100,
            output_tokens=200,
        )

        result = tailor_resume(db, job["id"])
        assert isinstance(result, TailoredResume)
        assert result.job_title == "Data Engineer"
        assert result.company_name == "TestCo"
        assert "Resume" in result.markdown
        assert result.requirements["required_skills"] == ["Python", "SQL", "Spark"]

    @patch("beacon.materials.resume.generate")
    @patch("beacon.materials.resume.generate_structured")
    def test_tailor_resume_uses_title_when_no_description(self, mock_structured, mock_generate, db):
        cid = _insert_company(db)
        job = upsert_job(db, cid, "ML Engineer", url="https://x.com/1")
        _populate_profile(db)

        mock_structured.return_value = {
            "required_skills": ["Python"], "preferred_skills": [],
            "seniority": "senior", "keywords": [], "responsibilities": [], "culture_signals": [],
        }
        mock_generate.return_value = LLMResponse(
            text="# Resume", model="test", input_tokens=10, output_tokens=20,
        )

        result = tailor_resume(db, job["id"])
        # Should have used the title "ML Engineer" as the description
        call_args = mock_structured.call_args[0][0]
        assert "ML Engineer" in call_args

    def test_tailor_resume_job_not_found(self, db):
        with pytest.raises(ValueError, match="not found"):
            tailor_resume(db, 99999)


class TestRenderMarkdown:
    def test_render_returns_markdown_text(self):
        resume = TailoredResume(
            job_id=1, job_title="Engineer", company_name="Co",
            markdown="# Test Resume\n## Skills\nPython",
        )
        result = render_markdown(resume)
        assert result == "# Test Resume\n## Skills\nPython"


class TestRenderDocx:
    def test_render_docx_missing_dep(self):
        from beacon.materials.renderer import render_docx
        resume = TailoredResume(
            job_id=1, job_title="Engineer", company_name="Co",
            markdown="# Test",
        )
        # python-docx is not installed, should raise RuntimeError
        with pytest.raises(RuntimeError, match="python-docx"):
            render_docx(resume, "/tmp/test.docx")


class TestRenderPdf:
    def test_render_pdf_missing_dep(self):
        from beacon.materials.renderer import render_pdf
        resume = TailoredResume(
            job_id=1, job_title="Engineer", company_name="Co",
            markdown="# Test",
        )
        # fpdf2 is not installed, should raise RuntimeError
        with pytest.raises(RuntimeError, match="fpdf2"):
            render_pdf(resume, "/tmp/test.pdf")
