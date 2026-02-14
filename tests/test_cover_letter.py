"""Tests for cover letter generator."""

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
from beacon.materials.cover_letter import (
    build_company_context,
    build_profile_summary,
    generate_cover_letter,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _insert_company(conn, name="TestCo"):
    conn.execute(
        "INSERT INTO companies (name, remote_policy, size_bucket, description, ai_first_score, tier) "
        "VALUES (?, 'hybrid', 'mid-200-1000', 'AI-first data company', 8.5, 1)",
        (name,),
    )
    conn.commit()
    return conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()["id"]


def _populate_company_research(conn, company_id):
    """Add Phase 1 research data for testing."""
    conn.execute(
        "INSERT INTO leadership_signals (company_id, leader_name, leader_title, signal_type, content, impact_level) "
        "VALUES (?, 'CEO Smith', 'CEO', 'quote', 'AI is our top priority', 'company-wide')",
        (company_id,),
    )
    conn.execute(
        "INSERT INTO ai_signals (company_id, signal_type, title, signal_strength) "
        "VALUES (?, 'engineering_blog', 'How We Use AI in Data Engineering', 4)",
        (company_id,),
    )
    conn.execute(
        "INSERT INTO tools_adopted (company_id, tool_name, adoption_level) "
        "VALUES (?, 'GitHub Copilot', 'required')",
        (company_id,),
    )
    conn.commit()


def _populate_profile(conn):
    """Add sample profile data."""
    add_work_experience(conn, "DataCo", "Senior Data Engineer", "2022-01",
                        key_achievements=["Reduced latency 50%", "Led team of 3"],
                        technologies=["Python", "Spark"])
    add_skill(conn, "Python", category="language", proficiency="expert")
    add_skill(conn, "SQL", category="language")
    add_project(conn, "Beacon", description="Job search tool")
    add_education(conn, "MIT", degree="MS", field_of_study="CS")


class TestBuildCompanyContext:
    def test_includes_company_info(self, db):
        cid = _insert_company(db)
        context = build_company_context(db, cid)
        assert "TestCo" in context
        assert "8.5" in context

    def test_includes_leadership_signals(self, db):
        cid = _insert_company(db)
        _populate_company_research(db, cid)
        context = build_company_context(db, cid)
        assert "CEO Smith" in context
        assert "AI is our top priority" in context

    def test_includes_ai_signals(self, db):
        cid = _insert_company(db)
        _populate_company_research(db, cid)
        context = build_company_context(db, cid)
        assert "engineering_blog" in context

    def test_includes_tools(self, db):
        cid = _insert_company(db)
        _populate_company_research(db, cid)
        context = build_company_context(db, cid)
        assert "GitHub Copilot" in context
        assert "required" in context

    def test_empty_company(self, db):
        context = build_company_context(db, 99999)
        assert context == ""


class TestBuildProfileSummary:
    def test_includes_work_experience(self, db):
        _populate_profile(db)
        summary = build_profile_summary(db)
        assert "DataCo" in summary
        assert "Senior Data Engineer" in summary

    def test_includes_skills(self, db):
        _populate_profile(db)
        summary = build_profile_summary(db)
        assert "Python" in summary

    def test_includes_education(self, db):
        _populate_profile(db)
        summary = build_profile_summary(db)
        assert "MIT" in summary

    def test_empty_profile(self, db):
        summary = build_profile_summary(db)
        assert summary == ""


class TestGenerateCoverLetter:
    @patch("beacon.materials.cover_letter.generate")
    @patch("beacon.materials.cover_letter.extract_requirements")
    def test_generates_cover_letter(self, mock_extract, mock_generate, db):
        cid = _insert_company(db)
        _populate_company_research(db, cid)
        _populate_profile(db)
        job = upsert_job(db, cid, "Data Engineer", url="https://x.com/1",
                         description_text="Looking for Python expert")

        mock_extract.return_value = {
            "required_skills": ["Python"], "preferred_skills": [],
            "seniority": "senior", "keywords": [],
        }
        mock_generate.return_value = LLMResponse(
            text="Dear Hiring Manager,\n\nI am writing to express...",
            model="test", input_tokens=100, output_tokens=200,
        )

        result = generate_cover_letter(db, job["id"])
        assert "Dear Hiring Manager" in result
        mock_generate.assert_called_once()

    @patch("beacon.materials.cover_letter.generate")
    @patch("beacon.materials.cover_letter.extract_requirements")
    def test_tone_parameter(self, mock_extract, mock_generate, db):
        cid = _insert_company(db)
        job = upsert_job(db, cid, "Engineer", url="https://x.com/1")

        mock_extract.return_value = {"required_skills": [], "preferred_skills": [], "seniority": "mid", "keywords": []}
        mock_generate.return_value = LLMResponse(
            text="Hey there!", model="test", input_tokens=10, output_tokens=20,
        )

        generate_cover_letter(db, job["id"], tone="conversational")
        call_kwargs = mock_generate.call_args
        assert "conversational" in call_kwargs[1]["system"]

    def test_job_not_found(self, db):
        with pytest.raises(ValueError, match="not found"):
            generate_cover_letter(db, 99999)
