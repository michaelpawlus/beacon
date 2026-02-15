"""Tests for Phase 4 presence CLI commands."""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.cli import app
from beacon.db.connection import get_connection, init_db
from beacon.db.content import add_calendar_entry, add_content_draft
from beacon.db.profile import add_project, add_skill, add_work_experience
from beacon.llm.client import LLMResponse

runner = CliRunner()

MOCK_LLM = "beacon.llm.client.generate"


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


def _populate_profile(conn):
    add_work_experience(conn, "TestCo", "Data Scientist", "2023-01",
                         key_achievements=["Led AI project"], technologies=["Python"])
    add_project(conn, "TestProject", description="A test project", technologies=["Python"])
    add_skill(conn, "Python", category="language", proficiency="expert")


class TestPresenceDrafts:
    def test_list_drafts_empty(self, db):
        conn, db_path = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "drafts"])
            assert result.exit_code == 0
            assert "No content drafts" in result.output

    def test_list_drafts_with_data(self, db):
        conn, db_path = db
        add_content_draft(conn, "readme", "github", "My README", "# Hello")
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "drafts"])
            assert result.exit_code == 0
            assert "My README" in result.output

    def test_show_draft(self, db):
        conn, db_path = db
        draft_id = add_content_draft(conn, "readme", "github", "My README", "# Hello World")
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "draft", str(draft_id)])
            assert result.exit_code == 0
            assert "My README" in result.output

    def test_show_draft_not_found(self, db):
        conn, db_path = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "draft", "999"])
            assert result.exit_code == 0
            assert "No draft found" in result.output

    def test_publish_draft(self, db):
        conn, db_path = db
        draft_id = add_content_draft(conn, "post", "linkedin", "Post", "body")
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "publish", str(draft_id), "--url", "https://example.com"])
            assert result.exit_code == 0
            assert "published" in result.output

    def test_publish_draft_not_found(self, db):
        conn, db_path = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "publish", "999"])
            assert result.exit_code == 0
            assert "No draft found" in result.output


class TestPresenceGitHub:
    @patch(MOCK_LLM)
    def test_github_readme(self, mock_generate, db):
        conn, db_path = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="# Hi, I'm Test\nData Scientist.", model="test",
            input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "github"])
            assert result.exit_code == 0
            assert "Hi, I'm Test" in result.output

    @patch(MOCK_LLM)
    def test_github_readme_with_output(self, mock_generate, db, tmp_path):
        conn, db_path = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="# README Content", model="test",
            input_tokens=100, output_tokens=50,
        )
        output_file = tmp_path / "README.md"
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "github", "--output", str(output_file)])
            assert result.exit_code == 0
            assert output_file.exists()
            assert "README Content" in output_file.read_text()


class TestPresenceLinkedIn:
    @patch(MOCK_LLM)
    def test_linkedin_headline(self, mock_generate, db):
        conn, db_path = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="1. Data Scientist | AI\n2. Building AI tools",
            model="test", input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "linkedin-headline"])
            assert result.exit_code == 0
            assert "Data Scientist" in result.output

    @patch(MOCK_LLM)
    def test_linkedin_about(self, mock_generate, db):
        conn, db_path = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="I build AI implementation infrastructure...",
            model="test", input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "linkedin-about"])
            assert result.exit_code == 0
            assert "AI implementation" in result.output

    @patch(MOCK_LLM)
    def test_linkedin_post(self, mock_generate, db):
        conn, db_path = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="Here's what I learned...", model="test",
            input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "linkedin-post", "--topic", "AI adoption"])
            assert result.exit_code == 0
            assert "learned" in result.output


class TestPresenceBlog:
    @patch(MOCK_LLM)
    def test_blog_outline(self, mock_generate, db):
        conn, db_path = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="# Outline\n## Section 1\n- Point", model="test",
            input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "blog-outline", "--topic", "AI agents"])
            assert result.exit_code == 0
            assert "Section 1" in result.output

    @patch(MOCK_LLM)
    def test_blog_generate(self, mock_generate, db):
        conn, db_path = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="---\ntitle: Test Post\n---\nContent here.",
            model="test", input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "blog-generate", "--topic", "AI"])
            assert result.exit_code == 0
            assert "Content here" in result.output

    def test_blog_export_not_found(self, db):
        conn, db_path = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "blog-export", "999"])
            assert result.exit_code == 1


class TestPresenceCalendar:
    def test_calendar_empty(self, db):
        conn, db_path = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "calendar"])
            assert result.exit_code == 0
            assert "No calendar entries" in result.output

    def test_calendar_with_entries(self, db):
        conn, db_path = db
        add_calendar_entry(conn, "AI Post", "linkedin", "post", target_date="2025-06-01")
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "calendar"])
            assert result.exit_code == 0
            assert "AI Post" in result.output

    def test_calendar_add(self, db):
        conn, db_path = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, [
                "presence", "calendar-add",
                "--title", "New Post",
                "--platform", "blog",
                "--date", "2025-07-01",
            ])
            assert result.exit_code == 0
            assert "created" in result.output

    @patch(MOCK_LLM)
    def test_calendar_seed(self, mock_generate, db):
        conn, db_path = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="1. Building AI Agents\n2. Data Warehouse Migration\n3. Copilot Rollout",
            model="test", input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "calendar-seed"])
            assert result.exit_code == 0
            assert "Created" in result.output
