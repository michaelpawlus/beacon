"""Tests for beacon.session — session logging and Obsidian note generation."""

import json
from unittest.mock import patch

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.session import (
    generate_session_note,
    get_session,
    list_sessions,
    save_session_to_db,
    slugify,
    write_session_note,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


# ── slugify ──────────────────────────────────────────────────────────


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert slugify("Built a REST API! (v2)") == "built-a-rest-api-v2"

    def test_truncation(self):
        result = slugify("a" * 100, max_length=10)
        assert len(result) <= 10

    def test_trailing_dash_stripped(self):
        result = slugify("hello-world-", max_length=12)
        assert not result.endswith("-")

    def test_multiple_spaces(self):
        assert slugify("lots   of   spaces") == "lots-of-spaces"


# ── generate_session_note ────────────────────────────────────────────


class TestGenerateSessionNote:
    def test_contains_frontmatter(self):
        note = generate_session_note("My Session", "Did stuff", session_date="2026-01-15")
        assert "---" in note
        assert "type: session-log" in note
        assert "date: 2026-01-15" in note

    def test_contains_title_and_summary(self):
        note = generate_session_note("Build Feature X", "Added feature X to the app")
        assert "# Build Feature X" in note
        assert "Added feature X to the app" in note

    def test_challenges_section(self):
        note = generate_session_note("T", "S", challenges=["Fixed auth bug", "Handled edge case"])
        assert "## Challenges & Solutions" in note
        assert "- Fixed auth bug" in note

    def test_technologies_section(self):
        note = generate_session_note("T", "S", technologies=["Python", "SQLite"])
        assert "## Technologies & Patterns" in note
        assert "- Python" in note

    def test_impact_section(self):
        note = generate_session_note("T", "S", impact="Reduced build time by 50%")
        assert "## Impact" in note
        assert "Reduced build time by 50%" in note

    def test_empty_optionals_no_sections(self):
        note = generate_session_note("T", "S")
        assert "## Challenges" not in note
        assert "## Technologies" not in note
        assert "## Impact" not in note

    def test_tags_in_frontmatter(self):
        note = generate_session_note("T", "S", project="beacon", tags=["portfolio"])
        assert "session-log" in note
        assert "beacon" in note
        assert "portfolio" in note

    def test_no_duplicate_tags(self):
        note = generate_session_note("T", "S", project="beacon", tags=["beacon", "portfolio"])
        lines = [line for line in note.split("\n") if line.startswith("tags:")]
        assert len(lines) == 1
        # "beacon" should only appear once in the tags line
        tag_line = lines[0]
        assert tag_line.count("beacon") == 1


# ── save_session_to_db ───────────────────────────────────────────────


class TestSaveSessionToDb:
    def test_insert_returns_id(self, db):
        sid = save_session_to_db(db, title="Test", summary="Summary")
        assert sid is not None
        assert sid > 0

    def test_json_serialization(self, db):
        sid = save_session_to_db(
            db, title="Test", summary="S",
            challenges=["c1"], technologies=["Python"], tags=["tag1"],
        )
        row = db.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        assert json.loads(row["challenges"]) == ["c1"]
        assert json.loads(row["technologies"]) == ["Python"]
        assert json.loads(row["tags"]) == ["tag1"]

    def test_defaults(self, db):
        sid = save_session_to_db(db, title="Test", summary="S")
        row = db.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        assert row["project"] == "beacon"
        assert row["session_date"] is not None


# ── list_sessions ────────────────────────────────────────────────────


class TestListSessions:
    def test_no_filter(self, db):
        save_session_to_db(db, title="A", summary="S")
        save_session_to_db(db, title="B", summary="S")
        result = list_sessions(db)
        assert len(result) == 2

    def test_project_filter(self, db):
        save_session_to_db(db, title="A", summary="S", project="beacon")
        save_session_to_db(db, title="B", summary="S", project="other")
        result = list_sessions(db, project="beacon")
        assert len(result) == 1
        assert result[0]["project"] == "beacon"

    def test_tag_filter(self, db):
        save_session_to_db(db, title="A", summary="S", tags=["portfolio"])
        save_session_to_db(db, title="B", summary="S", tags=["debug"])
        result = list_sessions(db, tag="portfolio")
        assert len(result) == 1

    def test_limit(self, db):
        for i in range(5):
            save_session_to_db(db, title=f"S{i}", summary="S")
        result = list_sessions(db, limit=3)
        assert len(result) == 3

    def test_ordering(self, db):
        save_session_to_db(db, title="Old", summary="S", session_date="2025-01-01")
        save_session_to_db(db, title="New", summary="S", session_date="2026-06-01")
        result = list_sessions(db)
        assert result[0]["title"] == "New"


# ── get_session ──────────────────────────────────────────────────────


class TestGetSession:
    def test_valid_id(self, db):
        sid = save_session_to_db(db, title="Test", summary="S")
        s = get_session(db, sid)
        assert s is not None
        assert s["title"] == "Test"

    def test_invalid_id(self, db):
        assert get_session(db, 9999) is None


# ── write_session_note ───────────────────────────────────────────────


class TestWriteSessionNote:
    def test_creates_dir_and_file(self, tmp_path):
        with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(tmp_path)}):
            path = write_session_note("# Note", "2026-03-13", "my-session")
            assert (tmp_path / "claude-sessions" / "2026-03-13-my-session.md").exists()
            assert path.endswith("2026-03-13-my-session.md")

    def test_content_written(self, tmp_path):
        with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(tmp_path)}):
            write_session_note("hello world", "2026-01-01", "test")
            content = (tmp_path / "claude-sessions" / "2026-01-01-test.md").read_text()
            assert content == "hello world"

    def test_missing_env_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(RuntimeError, match="OBSIDIAN_VAULT_PATH"):
                write_session_note("x", "2026-01-01", "t")


# ── CLI integration ─────────────────────────────────────────────────


class TestSessionCLI:
    def test_log_json(self, db, tmp_path):
        from typer.testing import CliRunner

        from beacon.cli import app

        with patch("beacon.cli.get_connection", return_value=db), \
             patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(tmp_path)}):
            runner = CliRunner()
            result = runner.invoke(app, [
                "session", "log", "Test Session",
                "--summary", "Did a thing",
                "--tag", "portfolio",
                "--json",
            ])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["id"] > 0
            assert data["title"] == "Test Session"

    def test_list_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        save_session_to_db(db, title="S1", summary="Summary")

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["session", "list", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert len(data) >= 1

    def test_show_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        sid = save_session_to_db(db, title="Show Me", summary="Details here")

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["session", "show", str(sid), "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["title"] == "Show Me"

    def test_show_not_found(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["session", "show", "9999", "--json"])
            assert result.exit_code == 2
