"""Tests for LinkedIn content generation and CLI commands."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.cli import app
from beacon.db.connection import get_connection, init_db
from beacon.db.profile import add_skill, add_work_experience
from beacon.llm.client import LLMResponse
from beacon.presence.adapters import adapt_for_linkedin

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
                         description="Building AI tools.", key_achievements=["Led AI rollout"],
                         technologies=["Python", "Databricks"])
    add_skill(conn, "Python", category="language", proficiency="expert")
    add_skill(conn, "AI Strategy", category="domain", proficiency="advanced")


class TestLinkedInHeadlineCLI:
    @patch(MOCK_LLM)
    def test_generates_multiple_options(self, mock_generate, db):
        conn, _ = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="1. Data Scientist | AI Implementation Lead\n"
                 "2. Building AI-Augmented Organizations\n"
                 "3. Data Scientist & AI Strategist\n"
                 "4. AI Implementation at Scale\n"
                 "5. Turning AI Hype into Enterprise Reality",
            model="test", input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "linkedin-headline"])
            assert result.exit_code == 0
            assert "1." in result.output
            assert "5." in result.output

    @patch(MOCK_LLM)
    def test_saves_as_draft(self, mock_generate, db):
        conn, _ = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="1. Option A\n2. Option B", model="test",
            input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "linkedin-headline"])
            assert "draft #" in result.output


class TestLinkedInAboutCLI:
    @patch(MOCK_LLM)
    def test_generates_about_section(self, mock_generate, db):
        conn, _ = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="I build AI implementation infrastructure for large organizations.\n\n"
                 "Currently at TestCo, where I lead AI agent development.",
            model="test", input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "linkedin-about"])
            assert result.exit_code == 0
            assert "AI implementation" in result.output

    @patch(MOCK_LLM)
    def test_adapts_for_linkedin_format(self, mock_generate, db):
        conn, _ = db
        _populate_profile(conn)
        # Return content with markdown that should be stripped
        mock_generate.return_value = LLMResponse(
            text="## About Me\n\nI **build** AI tools at *TestCo*.",
            model="test", input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "linkedin-about"])
            assert result.exit_code == 0
            # Markdown should be stripped
            assert "**" not in result.output
            assert "##" not in result.output


class TestLinkedInPostCLI:
    @patch(MOCK_LLM)
    def test_generates_post(self, mock_generate, db):
        conn, _ = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="Here's what I learned rolling out Copilot to 50K users.\n\n"
                 "Spoiler: it's not about the technology.",
            model="test", input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, [
                "presence", "linkedin-post",
                "--topic", "Rolling out Copilot at scale",
            ])
            assert result.exit_code == 0
            assert "learned" in result.output

    @patch(MOCK_LLM)
    def test_with_tone_option(self, mock_generate, db):
        conn, _ = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="So here's a story...", model="test",
            input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, [
                "presence", "linkedin-post",
                "--topic", "AI adoption",
                "--tone", "conversational",
            ])
            assert result.exit_code == 0


class TestLinkedInAdapter:
    def test_strips_markdown_for_linkedin(self):
        content = "## My Post\n\nThis is **important** and *urgent*.\n\n[Link](https://example.com)"
        result = adapt_for_linkedin(content)
        assert "##" not in result
        assert "**" not in result
        assert "*" not in result
        assert "important" in result

    def test_enforces_character_limit(self):
        long_content = "A " * 2000
        result = adapt_for_linkedin(long_content, max_chars=3000)
        assert len(result) <= 3000

    def test_about_section_limit(self):
        long_content = "Word " * 1000
        result = adapt_for_linkedin(long_content, max_chars=2600)
        assert len(result) <= 2600

    def test_preserves_plain_text(self):
        result = adapt_for_linkedin("Just plain text with line breaks.\n\nAnother paragraph.")
        assert "Just plain text" in result
        assert "Another paragraph" in result

    def test_strips_code_blocks(self):
        content = "Before\n\n```python\ndef hello():\n    print('hi')\n```\n\nAfter"
        result = adapt_for_linkedin(content)
        assert "```" not in result
        assert "Before" in result
        assert "After" in result
