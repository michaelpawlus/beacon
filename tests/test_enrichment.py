"""Tests for beacon.presence.enrichment — enrichment interview system."""

import json
from unittest.mock import MagicMock, call, patch

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.db.content import add_accomplishment, get_accomplishment_by_id, get_accomplishments
from beacon.db.profile import (
    add_education,
    add_project,
    add_publication,
    add_skill,
    add_work_experience,
)
from beacon.llm.client import LLMResponse
from beacon.presence.enrichment import (
    accomplishment_to_content,
    generate_missing_info_todos,
    run_enrichment_interview,
)

MOCK_LLM = "beacon.llm.client.generate"


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _populate_full_profile(conn):
    """Add a complete profile."""
    add_work_experience(
        conn, "Acme Corp", "Data Scientist", "2023-01",
        description="Building AI tools.",
        key_achievements=["Led AI project", "Built warehouse", "Deployed agents"],
        technologies=["Python", "Databricks"],
        metrics=["50K users"],
    )
    add_project(conn, "Beacon", description="Job search tool",
                 technologies=["Python"], repo_url="https://github.com/test", is_public=True)
    add_skill(conn, "Python", category="language", proficiency="expert")
    add_skill(conn, "SQL", category="language", proficiency="expert")
    add_skill(conn, "Databricks", category="tool", proficiency="advanced")
    add_skill(conn, "NLP", category="domain", proficiency="advanced")
    add_skill(conn, "pandas", category="framework", proficiency="expert")
    add_skill(conn, "PySpark", category="framework", proficiency="advanced")
    add_skill(conn, "scikit-learn", category="framework", proficiency="advanced")
    add_skill(conn, "Claude API", category="tool", proficiency="advanced")
    add_skill(conn, "Git", category="tool", proficiency="advanced")
    add_skill(conn, "AI Strategy", category="domain", proficiency="advanced")
    add_education(conn, "State University", degree="BS", field_of_study="CS")
    add_publication(conn, "Talk", "talk", venue="Conf")
    add_accomplishment(conn, "Led AI rollout", result="Adopted", metrics="50K users")


class TestGenerateMissingInfoTodos:
    def test_empty_profile_has_many_todos(self, db):
        todos = generate_missing_info_todos(db)
        assert len(todos) > 0
        assert any("education" in t.lower() for t in todos)
        assert any("work" in t.lower() for t in todos)

    def test_complete_profile_reports_complete(self, db):
        _populate_full_profile(db)
        todos = generate_missing_info_todos(db)
        assert any("[x]" in t for t in todos)

    def test_missing_education(self, db):
        add_work_experience(db, "Co", "Dev", "2023-01",
                             key_achievements=["A", "B", "C"], technologies=["Python"], metrics=["10x"])
        todos = generate_missing_info_todos(db)
        assert any("education" in t.lower() for t in todos)

    def test_missing_achievements(self, db):
        add_work_experience(db, "Co", "Dev", "2023-01")
        todos = generate_missing_info_todos(db)
        assert any("achievement" in t.lower() for t in todos)

    def test_missing_metrics(self, db):
        add_work_experience(db, "Co", "Dev", "2023-01",
                             key_achievements=["A", "B", "C"], technologies=["Python"])
        todos = generate_missing_info_todos(db)
        assert any("metric" in t.lower() for t in todos)

    def test_missing_technologies(self, db):
        add_work_experience(db, "Co", "Dev", "2023-01",
                             key_achievements=["A", "B", "C"], metrics=["10x"])
        todos = generate_missing_info_todos(db)
        assert any("technolog" in t.lower() for t in todos)

    def test_few_skills_warning(self, db):
        add_work_experience(db, "Co", "Dev", "2023-01",
                             key_achievements=["A", "B", "C"], technologies=["Py"], metrics=["10x"])
        add_skill(db, "Python", category="language")
        todos = generate_missing_info_todos(db)
        assert any("more skills" in t.lower() for t in todos)

    def test_missing_public_project(self, db):
        add_project(db, "Private", is_public=False)
        todos = generate_missing_info_todos(db)
        assert any("public project" in t.lower() for t in todos)

    def test_missing_publications(self, db):
        add_work_experience(db, "Co", "Dev", "2023-01")
        todos = generate_missing_info_todos(db)
        assert any("publication" in t.lower() for t in todos)

    def test_incomplete_accomplishments(self, db):
        add_accomplishment(db, "Did something")  # No result or metrics
        todos = generate_missing_info_todos(db)
        assert any("enrichment" in t.lower() for t in todos)

    def test_missing_description(self, db):
        add_work_experience(db, "Co", "Dev", "2023-01",
                             key_achievements=["A", "B", "C"], technologies=["Py"], metrics=["10x"])
        todos = generate_missing_info_todos(db)
        assert any("description" in t.lower() for t in todos)

    def test_missing_skill_categories(self, db):
        add_skill(db, "Python", category="language")
        todos = generate_missing_info_todos(db)
        assert any("categories" in t.lower() for t in todos)


class TestRunEnrichmentInterview:
    @patch("rich.prompt.Prompt")
    @patch("rich.prompt.Confirm")
    def test_saves_accomplishment(self, mock_confirm, mock_prompt, db):
        console = MagicMock()
        mock_prompt.ask.side_effect = [
            "Led Copilot rollout",  # statement
            "Large university needed AI",  # context
            "Built governance framework",  # action
            "Adopted across institution",  # result
            "50K users",  # metrics
            "Copilot, Python",  # technologies
            "CIO, department heads",  # stakeholders
            "3 months",  # timeline
            "Resistance from staff",  # challenges
            "Change management is key",  # learning
        ]
        result = run_enrichment_interview(console, db)
        assert result is not None
        assert result["statement"] == "Led Copilot rollout"
        assert result["context"] == "Large university needed AI"

        # Verify saved in DB
        accs = get_accomplishments(db)
        assert len(accs) == 1
        assert accs[0]["raw_statement"] == "Led Copilot rollout"

    @patch("rich.prompt.Prompt")
    @patch("rich.prompt.Confirm")
    def test_empty_statement_returns_none(self, mock_confirm, mock_prompt, db):
        console = MagicMock()
        mock_prompt.ask.return_value = ""
        result = run_enrichment_interview(console, db)
        assert result is None

    @patch("rich.prompt.Prompt")
    @patch("rich.prompt.Confirm")
    def test_with_work_experience_id(self, mock_confirm, mock_prompt, db):
        work_id = add_work_experience(db, "Acme", "Dev", "2023-01")
        console = MagicMock()
        mock_prompt.ask.side_effect = [
            "Built feature",  # statement
            "", "", "", "", "", "", "", "", "",  # all other fields empty
        ]
        result = run_enrichment_interview(console, db, work_experience_id=work_id)
        assert result is not None
        accs = get_accomplishments(db)
        assert accs[0]["work_experience_id"] == work_id

    @patch(MOCK_LLM)
    @patch("rich.prompt.Prompt")
    @patch("rich.prompt.Confirm")
    def test_generate_content_flag(self, mock_confirm, mock_prompt, mock_generate, db):
        console = MagicMock()
        mock_prompt.ask.side_effect = [
            "Built AI agents",  # statement
            "University needed automation",  # context
            "Designed and deployed agents",  # action
            "Agents serving 500 users",  # result
            "500 users, 10x faster",  # metrics
            "Python, Claude API",  # technologies
            "IT team", "2 months", "Security concerns", "Start small",
        ]
        mock_generate.return_value = LLMResponse(
            text="LinkedIn: Hook about agents\nBlog: How I built agents",
            model="test", input_tokens=100, output_tokens=50,
        )
        result = run_enrichment_interview(console, db, generate_content=True)
        assert result is not None
        mock_generate.assert_called_once()


class TestAccomplishmentToContent:
    @patch(MOCK_LLM)
    def test_generates_content(self, mock_generate, db):
        acc_id = add_accomplishment(
            db, "Led Copilot rollout",
            context="Large university", action="Built framework",
            result="Adopted", metrics="50K users",
        )
        mock_generate.return_value = LLMResponse(
            text="LinkedIn: Great hook\nBlog: Copilot Story\nBullet: Led rollout",
            model="test", input_tokens=100, output_tokens=50,
        )
        result = accomplishment_to_content(db, acc_id)
        assert result is not None
        assert "content_angles" in result

    def test_not_found_returns_none(self, db):
        result = accomplishment_to_content(db, 999)
        assert result is None

    @patch(MOCK_LLM)
    def test_includes_raw_statement(self, mock_generate, db):
        acc_id = add_accomplishment(db, "Built data warehouse")
        mock_generate.return_value = LLMResponse(
            text="angles", model="test", input_tokens=100, output_tokens=50,
        )
        result = accomplishment_to_content(db, acc_id)
        assert result["raw_statement"] == "Built data warehouse"
