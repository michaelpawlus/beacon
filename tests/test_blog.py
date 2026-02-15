"""Tests for blog generation and export CLI commands."""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.cli import app
from beacon.db.connection import get_connection, init_db
from beacon.db.content import add_content_draft
from beacon.db.profile import add_skill, add_work_experience
from beacon.llm.client import LLMResponse
from beacon.presence.adapters import adapt_for_blog_markdown

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
                         key_achievements=["Built AI agents"], technologies=["Python"])
    add_skill(conn, "Python", category="language", proficiency="expert")


class TestBlogOutlineCLI:
    @patch(MOCK_LLM)
    def test_outline_generates(self, mock_generate, db):
        conn, db_path = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="# Outline\n## Introduction\n## Main Points\n## Conclusion",
            model="test", input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "blog-outline", "--topic", "AI agents"])
            assert result.exit_code == 0
            assert "Outline" in result.output
            assert "draft #" in result.output


class TestBlogGenerateCLI:
    @patch(MOCK_LLM)
    def test_generate_creates_draft(self, mock_generate, db):
        conn, db_path = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="---\ntitle: AI Agents\n---\nFull blog post content about building AI agents.",
            model="test", input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "blog-generate", "--topic", "AI agents"])
            assert result.exit_code == 0
            assert "blog post content" in result.output

    @patch(MOCK_LLM)
    def test_generate_saves_to_file(self, mock_generate, db, tmp_path):
        conn, db_path = db
        _populate_profile(conn)
        mock_generate.return_value = LLMResponse(
            text="Blog content here.", model="test",
            input_tokens=100, output_tokens=50,
        )
        output_file = tmp_path / "post.md"
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "blog-generate", "--topic", "AI",
                                          "--output", str(output_file)])
            assert result.exit_code == 0
            assert output_file.exists()


class TestBlogExportCLI:
    def test_export_astro(self, db):
        conn, db_path = db
        draft_id = add_content_draft(conn, "post", "blog", "My Post",
                                      "Blog content here.", metadata=json.dumps({"tags": ["ai"]}))
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "blog-export", str(draft_id), "--format", "astro"])
            assert result.exit_code == 0
            assert "---" in result.output
            assert "My Post" in result.output

    def test_export_medium(self, db):
        conn, db_path = db
        draft_id = add_content_draft(conn, "post", "blog", "My Post",
                                      "---\ntitle: Test\n---\nBlog content.")
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "blog-export", str(draft_id), "--format", "medium"])
            assert result.exit_code == 0
            assert "Blog content" in result.output

    def test_export_devto(self, db):
        conn, db_path = db
        draft_id = add_content_draft(conn, "post", "blog", "My Post", "Content.")
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "blog-export", str(draft_id), "--format", "devto"])
            assert result.exit_code == 0
            assert "published: false" in result.output

    def test_export_to_file(self, db, tmp_path):
        conn, db_path = db
        draft_id = add_content_draft(conn, "post", "blog", "My Post", "Content here.")
        output_file = tmp_path / "export.md"
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "blog-export", str(draft_id),
                                          "--format", "astro", "--output", str(output_file)])
            assert result.exit_code == 0
            assert output_file.exists()

    def test_export_unknown_format(self, db):
        conn, db_path = db
        draft_id = add_content_draft(conn, "post", "blog", "Post", "Content.")
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "blog-export", str(draft_id), "--format", "wordpress"])
            assert result.exit_code == 1


class TestBlogFrontmatter:
    def test_frontmatter_includes_title(self):
        result = adapt_for_blog_markdown("Content", title="My Post")
        assert 'title: "My Post"' in result

    def test_frontmatter_includes_tags(self):
        result = adapt_for_blog_markdown("Content", tags=["python", "ai", "data"])
        assert "tags: [python, ai, data]" in result

    def test_frontmatter_includes_draft_flag(self):
        result = adapt_for_blog_markdown("Content")
        assert "draft: true" in result

    def test_existing_frontmatter_preserved(self):
        content = "---\ntitle: Existing\ntags: [original]\n---\nBody"
        result = adapt_for_blog_markdown(content, title="New Title")
        assert "Existing" in result
        assert "New Title" not in result
