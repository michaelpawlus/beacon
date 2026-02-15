"""Tests for beacon.presence.generator — content generation engine."""

import json
from unittest.mock import patch

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.db.profile import (
    add_education,
    add_project,
    add_publication,
    add_skill,
    add_work_experience,
)
from beacon.llm.client import LLMResponse
from beacon.presence.generator import (
    build_full_profile_context,
    generate_blog_outline,
    generate_blog_post,
    generate_content_angles,
    generate_content_ideas,
    generate_enrichment_questions,
    generate_github_readme,
    generate_linkedin_about,
    generate_linkedin_headline,
    generate_linkedin_post,
)

MOCK_LLM = "beacon.llm.client.generate"


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _populate_profile(conn):
    """Add sample profile data for testing."""
    add_work_experience(
        conn, "Acme Corp", "Data Scientist", "2023-01",
        description="Building AI tools for enterprise.",
        key_achievements=["Led AI agent development", "Modernized data warehouse"],
        technologies=["Python", "Databricks", "Claude API"],
        metrics=["50K users impacted"],
    )
    add_work_experience(
        conn, "BigCo University", "Analyst", "2020-01", end_date="2022-12",
        description="Analytics for advancement operations.",
        key_achievements=["Built propensity models"],
        technologies=["Python", "R", "SQL"],
    )
    add_project(
        conn, "Beacon",
        description="AI-powered job search platform",
        technologies=["Python", "SQLite", "Typer"],
        outcomes=["38 companies scored", "274 tests passing"],
        repo_url="https://github.com/example/beacon",
        is_public=True,
    )
    add_skill(conn, "Python", category="language", proficiency="expert", years_experience=7)
    add_skill(conn, "SQL", category="language", proficiency="expert", years_experience=10)
    add_skill(conn, "Databricks", category="tool", proficiency="advanced", years_experience=3)
    add_skill(conn, "NLP", category="domain", proficiency="advanced")
    add_education(conn, "State University", degree="BS", field_of_study="Computer Science")
    add_publication(conn, "DRIVE 2017 Talk", "talk", venue="DRIVE Conference", date_published="2017")


class TestBuildFullProfileContext:
    def test_empty_profile_returns_empty(self, db):
        context = build_full_profile_context(db)
        assert context == ""

    def test_includes_work_experience(self, db):
        _populate_profile(db)
        context = build_full_profile_context(db)
        assert "Acme Corp" in context
        assert "Data Scientist" in context
        assert "2023-01" in context

    def test_includes_achievements(self, db):
        _populate_profile(db)
        context = build_full_profile_context(db)
        assert "Led AI agent development" in context

    def test_includes_technologies(self, db):
        _populate_profile(db)
        context = build_full_profile_context(db)
        assert "Python" in context
        assert "Databricks" in context

    def test_includes_skills_by_category(self, db):
        _populate_profile(db)
        context = build_full_profile_context(db)
        assert "language:" in context
        assert "tool:" in context
        assert "domain:" in context

    def test_includes_projects(self, db):
        _populate_profile(db)
        context = build_full_profile_context(db)
        assert "Beacon" in context
        assert "AI-powered job search" in context

    def test_includes_education(self, db):
        _populate_profile(db)
        context = build_full_profile_context(db)
        assert "State University" in context
        assert "Computer Science" in context

    def test_includes_publications(self, db):
        _populate_profile(db)
        context = build_full_profile_context(db)
        assert "DRIVE 2017 Talk" in context

    def test_includes_outcomes(self, db):
        _populate_profile(db)
        context = build_full_profile_context(db)
        assert "274 tests passing" in context

    def test_current_role_shows_present(self, db):
        _populate_profile(db)
        context = build_full_profile_context(db)
        assert "Present" in context


class TestGenerateGitHubReadme:
    @patch(MOCK_LLM)
    def test_generates_readme(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(
            text="# Hi, I'm Test User\nData Scientist building AI tools.",
            model="test", input_tokens=100, output_tokens=50,
        )
        result = generate_github_readme(db)
        assert "Hi, I'm Test User" in result
        mock_generate.assert_called_once()

    @patch(MOCK_LLM)
    def test_passes_profile_context(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(text="README", model="test", input_tokens=100, output_tokens=50)
        generate_github_readme(db)
        call_args = mock_generate.call_args
        assert "Acme Corp" in call_args[0][0]

    @patch(MOCK_LLM)
    def test_uses_github_system_prompt(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(text="README", model="test", input_tokens=100, output_tokens=50)
        generate_github_readme(db)
        call_kwargs = mock_generate.call_args[1]
        assert "GitHub profile README" in call_kwargs["system"]


class TestGenerateLinkedInHeadline:
    @patch(MOCK_LLM)
    def test_generates_headlines(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(
            text="1. Data Scientist | AI Implementation\n2. Building AI tools at scale",
            model="test", input_tokens=100, output_tokens=50,
        )
        result = generate_linkedin_headline(db)
        assert "1." in result
        assert "2." in result

    @patch(MOCK_LLM)
    def test_uses_linkedin_system_prompt(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(text="headlines", model="test", input_tokens=100, output_tokens=50)
        generate_linkedin_headline(db)
        call_kwargs = mock_generate.call_args[1]
        assert "LinkedIn" in call_kwargs["system"]


class TestGenerateLinkedInAbout:
    @patch(MOCK_LLM)
    def test_generates_about(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(
            text="I build AI implementation infrastructure...",
            model="test", input_tokens=100, output_tokens=50,
        )
        result = generate_linkedin_about(db)
        assert "AI implementation" in result

    @patch(MOCK_LLM)
    def test_uses_full_context(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(text="about", model="test", input_tokens=100, output_tokens=50)
        generate_linkedin_about(db)
        call_args = mock_generate.call_args[0][0]
        assert "key_achievements" not in call_args or "Led AI agent" in call_args


class TestGenerateLinkedInPost:
    @patch(MOCK_LLM)
    def test_generates_post(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(
            text="Here's what I learned rolling out AI tools...",
            model="test", input_tokens=100, output_tokens=50,
        )
        result = generate_linkedin_post(db, "AI adoption in higher ed")
        assert "learned" in result

    @patch(MOCK_LLM)
    def test_includes_topic_in_prompt(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(text="post", model="test", input_tokens=100, output_tokens=50)
        generate_linkedin_post(db, "Databricks migration tips")
        call_args = mock_generate.call_args[0][0]
        assert "Databricks migration tips" in call_args

    @patch(MOCK_LLM)
    def test_includes_tone(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(text="post", model="test", input_tokens=100, output_tokens=50)
        generate_linkedin_post(db, "AI", tone="conversational")
        call_args = mock_generate.call_args[0][0]
        assert "conversational" in call_args


class TestGenerateBlogOutline:
    @patch(MOCK_LLM)
    def test_generates_outline(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(
            text="# Blog Outline\n## Section 1\n- Point A",
            model="test", input_tokens=100, output_tokens=50,
        )
        result = generate_blog_outline(db, "Building AI agents")
        assert "Section 1" in result

    @patch(MOCK_LLM)
    def test_includes_topic(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(text="outline", model="test", input_tokens=100, output_tokens=50)
        generate_blog_outline(db, "Data warehouse modernization")
        call_args = mock_generate.call_args[0][0]
        assert "Data warehouse modernization" in call_args


class TestGenerateBlogPost:
    @patch(MOCK_LLM)
    def test_generates_post(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(
            text="---\ntitle: Test\n---\nContent here.",
            model="test", input_tokens=100, output_tokens=50,
        )
        result = generate_blog_post(db, "AI in higher ed")
        assert "Content here" in result

    @patch(MOCK_LLM)
    def test_uses_higher_max_tokens(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(text="post", model="test", input_tokens=100, output_tokens=50)
        generate_blog_post(db, "topic")
        call_kwargs = mock_generate.call_args[1]
        assert call_kwargs["max_tokens"] == 8192


class TestGenerateContentIdeas:
    @patch(MOCK_LLM)
    def test_generates_ideas(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(
            text="1. Building AI agents for non-technical users\n2. Data warehouse migration stories",
            model="test", input_tokens=100, output_tokens=50,
        )
        result = generate_content_ideas(db)
        assert "1." in result

    @patch(MOCK_LLM)
    def test_uses_high_temperature(self, mock_generate, db):
        _populate_profile(db)
        mock_generate.return_value = LLMResponse(text="ideas", model="test", input_tokens=100, output_tokens=50)
        generate_content_ideas(db)
        call_kwargs = mock_generate.call_args[1]
        assert call_kwargs["temperature"] == 0.9


class TestGenerateEnrichmentQuestions:
    @patch(MOCK_LLM)
    def test_generates_questions(self, mock_generate):
        mock_generate.return_value = LLMResponse(
            text="1. What was the situation?\n2. What did you do?",
            model="test", input_tokens=100, output_tokens=50,
        )
        result = generate_enrichment_questions("Rolled out Copilot to 50K users")
        assert "1." in result

    @patch(MOCK_LLM)
    def test_includes_statement(self, mock_generate):
        mock_generate.return_value = LLMResponse(text="questions", model="test", input_tokens=100, output_tokens=50)
        generate_enrichment_questions("Built AI agents for donor correspondence")
        call_args = mock_generate.call_args[0][0]
        assert "Built AI agents for donor correspondence" in call_args

    @patch(MOCK_LLM)
    def test_includes_work_context(self, mock_generate):
        mock_generate.return_value = LLMResponse(text="questions", model="test", input_tokens=100, output_tokens=50)
        generate_enrichment_questions("Led project", work_context="Data Scientist at Acme Corp")
        call_args = mock_generate.call_args[0][0]
        assert "Acme Corp" in call_args


class TestGenerateContentAngles:
    @patch(MOCK_LLM)
    def test_generates_angles(self, mock_generate):
        mock_generate.return_value = LLMResponse(
            text="1. LinkedIn: Hook about AI agents\n2. Blog: How I built agents\n3. Bullet: Led AI agent rollout",
            model="test", input_tokens=100, output_tokens=50,
        )
        result = generate_content_angles("Rolled out AI agents to 500 users")
        assert "LinkedIn" in result or "Blog" in result
