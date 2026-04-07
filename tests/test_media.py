"""Tests for beacon.media — media log tracking and team sharing."""

import json
from unittest.mock import patch

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.media import (
    add_media,
    export_for_list,
    export_list_csv,
    export_team_markdown,
    get_media,
    get_team_list,
    list_media,
    update_media,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _add_sample(conn, **overrides):
    defaults = {
        "title": "Test Video",
        "source_type": "video",
        "url": "https://example.com/video",
        "creator": "Test Creator",
        "platform": "YouTube",
        "rating": 4,
        "tags": ["ai", "coding"],
        "key_takeaways": "Learned something cool",
        "personal_reaction": "Really resonated with me",
    }
    # Allow passing share_category, why_it_matters, key_quotes through overrides
    defaults.update(overrides)
    return add_media(conn, **defaults)


# ── add_media ───────────────────────────────────────────────────────


class TestAddMedia:
    def test_returns_id(self, db):
        mid = add_media(db, title="Video A", source_type="video")
        assert mid is not None
        assert mid > 0

    def test_stores_all_fields(self, db):
        mid = _add_sample(db)
        row = db.execute("SELECT * FROM media_log WHERE id = ?", (mid,)).fetchone()
        assert row["title"] == "Test Video"
        assert row["source_type"] == "video"
        assert row["creator"] == "Test Creator"
        assert row["platform"] == "YouTube"
        assert row["rating"] == 4
        assert json.loads(row["tags"]) == ["ai", "coding"]
        assert row["key_takeaways"] == "Learned something cool"
        assert row["personal_reaction"] == "Really resonated with me"

    def test_date_defaults_to_today(self, db):
        mid = add_media(db, title="V", source_type="video")
        row = db.execute("SELECT * FROM media_log WHERE id = ?", (mid,)).fetchone()
        assert row["date_consumed"] is not None

    def test_team_shareable(self, db):
        mid = add_media(db, title="V", source_type="video", team_shareable=True, share_note="Watch this")
        row = db.execute("SELECT * FROM media_log WHERE id = ?", (mid,)).fetchone()
        assert row["team_shareable"] == 1
        assert row["share_note"] == "Watch this"

    def test_tags_json_serialization(self, db):
        mid = add_media(db, title="V", source_type="podcast", tags=["ai", "leadership"])
        row = db.execute("SELECT * FROM media_log WHERE id = ?", (mid,)).fetchone()
        assert json.loads(row["tags"]) == ["ai", "leadership"]


# ── list_media ──────────────────────────────────────────────────────


class TestListMedia:
    def test_returns_all(self, db):
        _add_sample(db, title="A")
        _add_sample(db, title="B")
        result = list_media(db)
        assert len(result) == 2

    def test_filter_source_type(self, db):
        _add_sample(db, title="Vid", source_type="video")
        _add_sample(db, title="Pod", source_type="podcast")
        result = list_media(db, source_type="video")
        assert len(result) == 1
        assert result[0]["title"] == "Vid"

    def test_filter_tag(self, db):
        _add_sample(db, title="A", tags=["ai"])
        _add_sample(db, title="B", tags=["cooking"])
        result = list_media(db, tag="ai")
        assert len(result) == 1
        assert result[0]["title"] == "A"

    def test_filter_min_rating(self, db):
        _add_sample(db, title="Low", rating=2)
        _add_sample(db, title="High", rating=5)
        result = list_media(db, min_rating=4)
        assert len(result) == 1
        assert result[0]["title"] == "High"

    def test_filter_team_only(self, db):
        _add_sample(db, title="Private")
        _add_sample(db, title="Shared", team_shareable=True)
        result = list_media(db, team_only=True)
        assert len(result) == 1
        assert result[0]["title"] == "Shared"

    def test_filter_since(self, db):
        _add_sample(db, title="Old", date_consumed="2024-01-01")
        _add_sample(db, title="New", date_consumed="2026-03-01")
        result = list_media(db, since="2026-01-01")
        assert len(result) == 1
        assert result[0]["title"] == "New"

    def test_search(self, db):
        _add_sample(db, title="AI Revolution", key_takeaways="transformers are key")
        _add_sample(db, title="Cooking Show", key_takeaways="use more salt")
        result = list_media(db, search="transformers")
        assert len(result) == 1
        assert result[0]["title"] == "AI Revolution"

    def test_limit(self, db):
        for i in range(5):
            _add_sample(db, title=f"V{i}")
        result = list_media(db, limit=3)
        assert len(result) == 3

    def test_ordering(self, db):
        _add_sample(db, title="Old", date_consumed="2024-01-01")
        _add_sample(db, title="New", date_consumed="2026-06-01")
        result = list_media(db)
        assert result[0]["title"] == "New"

    def test_composable_filters(self, db):
        _add_sample(db, title="Match", source_type="video", rating=5, tags=["ai"])
        _add_sample(db, title="WrongType", source_type="podcast", rating=5, tags=["ai"])
        _add_sample(db, title="LowRating", source_type="video", rating=2, tags=["ai"])
        result = list_media(db, source_type="video", min_rating=4, tag="ai")
        assert len(result) == 1
        assert result[0]["title"] == "Match"


# ── get_media ───────────────────────────────────────────────────────


class TestGetMedia:
    def test_valid_id(self, db):
        mid = _add_sample(db)
        entry = get_media(db, mid)
        assert entry is not None
        assert entry["title"] == "Test Video"

    def test_invalid_id(self, db):
        assert get_media(db, 9999) is None


# ── update_media ────────────────────────────────────────────────────


class TestUpdateMedia:
    def test_update_reaction(self, db):
        mid = _add_sample(db)
        ok = update_media(db, mid, personal_reaction="Changed my mind")
        assert ok is True
        entry = get_media(db, mid)
        assert entry["personal_reaction"] == "Changed my mind"

    def test_update_rating(self, db):
        mid = _add_sample(db, rating=3)
        update_media(db, mid, rating=5)
        entry = get_media(db, mid)
        assert entry["rating"] == 5

    def test_update_shareable(self, db):
        mid = _add_sample(db)
        update_media(db, mid, team_shareable=True, share_note="Great for the team")
        entry = get_media(db, mid)
        assert entry["team_shareable"] == 1
        assert entry["share_note"] == "Great for the team"

    def test_update_tags(self, db):
        mid = _add_sample(db, tags=["old"])
        update_media(db, mid, tags=["new", "updated"])
        entry = get_media(db, mid)
        assert json.loads(entry["tags"]) == ["new", "updated"]

    def test_update_not_found(self, db):
        ok = update_media(db, 9999, rating=5)
        assert ok is False

    def test_update_no_fields(self, db):
        mid = _add_sample(db)
        ok = update_media(db, mid)
        assert ok is False


# ── get_team_list ───────────────────────────────────────────────────


class TestGetTeamList:
    def test_only_shareable(self, db):
        _add_sample(db, title="Private", team_shareable=False)
        _add_sample(db, title="Shared", team_shareable=True, share_note="Watch this")
        result = get_team_list(db)
        assert len(result) == 1
        assert result[0]["title"] == "Shared"

    def test_returns_limited_fields(self, db):
        _add_sample(db, title="Shared", team_shareable=True, personal_reaction="Deep thoughts")
        result = get_team_list(db)
        assert "personal_reaction" not in result[0]
        assert "key_takeaways" not in result[0]
        assert "share_note" in result[0]


# ── export_team_markdown ────────────────────────────────────────────


class TestExportTeamMarkdown:
    def test_empty(self):
        md = export_team_markdown([])
        assert "No team-shareable media" in md

    def test_renders_entries(self):
        entries = [
            {
                "id": 1,
                "title": "Great Video",
                "url": "https://example.com",
                "source_type": "video",
                "creator": "AI Expert",
                "platform": "YouTube",
                "date_consumed": "2026-03-01",
                "rating": 5,
                "tags": '["ai"]',
                "share_note": "Must watch for the team",
            }
        ]
        md = export_team_markdown(entries)
        assert "# Recommended AI Content" in md
        assert "[Great Video](https://example.com)" in md
        assert "AI Expert" in md
        assert "Must watch for the team" in md
        assert "⭐" in md

    def test_no_url_uses_plain_title(self):
        entries = [
            {
                "id": 1,
                "title": "Offline Talk",
                "url": None,
                "source_type": "talk",
                "creator": None,
                "platform": None,
                "date_consumed": "2026-03-01",
                "rating": None,
                "tags": None,
                "share_note": None,
            }
        ]
        md = export_team_markdown(entries)
        assert "- Offline Talk" in md


# ── new sharing fields ─────────────────────────────────────────────


class TestSharingFields:
    def test_add_with_sharing_fields(self, db):
        mid = add_media(
            db, title="AI Talk", source_type="video",
            why_it_matters="Shows how AI agents reduce onboarding time",
            key_quotes=["Agents are the new APIs", "Context is everything"],
            share_category="AI Adoption",
            team_shareable=True,
        )
        row = db.execute("SELECT * FROM media_log WHERE id = ?", (mid,)).fetchone()
        assert row["why_it_matters"] == "Shows how AI agents reduce onboarding time"
        assert json.loads(row["key_quotes"]) == ["Agents are the new APIs", "Context is everything"]
        assert row["share_category"] == "AI Adoption"

    def test_update_sharing_fields(self, db):
        mid = _add_sample(db)
        update_media(db, mid, why_it_matters="Critical for team", key_quotes=["Quote 1"], share_category="Leadership")
        entry = get_media(db, mid)
        assert entry["why_it_matters"] == "Critical for team"
        assert json.loads(entry["key_quotes"]) == ["Quote 1"]
        assert entry["share_category"] == "Leadership"

    def test_team_list_includes_new_fields(self, db):
        _add_sample(db, title="Shared", team_shareable=True, why_it_matters="Important", share_category="Technical")
        result = get_team_list(db)
        assert result[0]["why_it_matters"] == "Important"
        assert result[0]["share_category"] == "Technical"


# ── export_for_list ────────────────────────────────────────────────


class TestExportForList:
    def test_flat_columns(self, db):
        _add_sample(
            db, title="AI Video", team_shareable=True, share_note="Watch this",
            why_it_matters="Key insight", share_category="AI Adoption",
            key_takeaways="Transformers explained",
        )
        rows = export_for_list(db)
        assert len(rows) == 1
        r = rows[0]
        assert r["Title"] == "AI Video"
        assert r["WhyItMatters"] == "Key insight"
        assert r["Category"] == "AI Adoption"
        assert r["KeyPoints"] == "Transformers explained"
        assert r["ShareNote"] == "Watch this"

    def test_json_arrays_flattened(self, db):
        add_media(
            db, title="Quotable", source_type="video", team_shareable=True,
            tags=["ai", "agents"], key_quotes=["Quote A", "Quote B"],
        )
        rows = export_for_list(db)
        assert rows[0]["Tags"] == "ai, agents"
        assert rows[0]["KeyQuotes"] == "Quote A; Quote B"

    def test_only_shareable(self, db):
        _add_sample(db, title="Private")
        _add_sample(db, title="Shared", team_shareable=True)
        rows = export_for_list(db)
        assert len(rows) == 1
        assert rows[0]["Title"] == "Shared"

    def test_filter_by_category(self, db):
        _add_sample(db, title="A", team_shareable=True, share_category="AI Adoption")
        _add_sample(db, title="B", team_shareable=True, share_category="Leadership")
        rows = export_for_list(db, category="Leadership")
        assert len(rows) == 1
        assert rows[0]["Title"] == "B"

    def test_empty_fields_are_strings(self, db):
        add_media(db, title="Minimal", source_type="video", team_shareable=True)
        rows = export_for_list(db)
        r = rows[0]
        assert r["Creator"] == ""
        assert r["Category"] == ""
        assert r["WhyItMatters"] == ""
        assert r["KeyQuotes"] == ""


# ── export_list_csv ────────────────────────────────────────────────


class TestExportListCSV:
    def test_csv_output(self, db):
        _add_sample(db, title="CSV Test", team_shareable=True, share_category="Technical")
        rows = export_for_list(db)
        csv_str = export_list_csv(rows)
        assert "Title,URL,Type,Creator,Category" in csv_str
        assert "CSV Test" in csv_str
        assert "Technical" in csv_str

    def test_empty_csv(self):
        csv_str = export_list_csv([])
        assert csv_str == ""


# ── CLI integration ─────────────────────────────────────────────────


class TestMediaCLI:
    def test_add_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, [
                "media", "add", "AI Frontiers Talk",
                "--type", "video",
                "--creator", "Andrej Karpathy",
                "--rating", "5",
                "--json",
            ])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["id"] > 0
            assert data["title"] == "AI Frontiers Talk"

    def test_list_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        _add_sample(db, title="Listed Entry")

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["media", "list", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert len(data) >= 1

    def test_show_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        mid = _add_sample(db, title="Show Me")

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["media", "show", str(mid), "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["title"] == "Show Me"

    def test_show_not_found(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["media", "show", "9999", "--json"])
            assert result.exit_code == 2

    def test_update_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        mid = _add_sample(db, title="To Update")

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, [
                "media", "update", str(mid),
                "--rating", "5",
                "--reaction", "Even better on rewatch",
                "--json",
            ])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["updated"] is True

    def test_team_list_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        _add_sample(db, title="Team Pick", team_shareable=True, share_note="Great intro")

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["media", "team-list", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert len(data) >= 1
            assert data[0]["title"] == "Team Pick"

    def test_team_list_markdown_output(self, db, tmp_path):
        from typer.testing import CliRunner

        from beacon.cli import app

        _add_sample(db, title="Team Pick", team_shareable=True, share_note="Great intro", url="https://example.com")
        out_file = tmp_path / "team.md"

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["media", "team-list", "--output", str(out_file)])
            assert result.exit_code == 0
            content = out_file.read_text()
            assert "Team Pick" in content
            assert "Great intro" in content

    def test_add_with_sharing_fields(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        db_path = db.execute("PRAGMA database_list").fetchone()[2]

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, [
                "media", "add", "Agent Talk",
                "--type", "video",
                "--shareable",
                "--why", "Shows practical agent patterns",
                "--quote", "Agents are the new APIs",
                "--quote", "Context is everything",
                "--category", "AI Adoption",
                "--json",
            ])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            mid = data["id"]

        verify = get_connection(db_path)
        entry = get_media(verify, mid)
        verify.close()
        assert entry["why_it_matters"] == "Shows practical agent patterns"
        assert json.loads(entry["key_quotes"]) == ["Agents are the new APIs", "Context is everything"]
        assert entry["share_category"] == "AI Adoption"

    def test_update_sharing_fields(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        mid = _add_sample(db, title="To Enrich")
        db_path = db.execute("PRAGMA database_list").fetchone()[2]

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, [
                "media", "update", str(mid),
                "--why", "Critical for AI strategy",
                "--quote", "Key line here",
                "--category", "Leadership",
                "--json",
            ])
            assert result.exit_code == 0

        verify = get_connection(db_path)
        entry = get_media(verify, mid)
        verify.close()
        assert entry["why_it_matters"] == "Critical for AI strategy"
        assert json.loads(entry["key_quotes"]) == ["Key line here"]
        assert entry["share_category"] == "Leadership"

    def test_export_list_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        _add_sample(db, title="Export Me", team_shareable=True, share_category="Technical")

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["media", "export-list", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert len(data) >= 1
            assert data[0]["Title"] == "Export Me"
            assert data[0]["Category"] == "Technical"

    def test_export_list_csv(self, db, tmp_path):
        from typer.testing import CliRunner

        from beacon.cli import app

        _add_sample(db, title="CSV Export", team_shareable=True, share_category="AI Adoption")
        out_file = tmp_path / "export.csv"

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, [
                "media", "export-list",
                "--format", "csv",
                "--output", str(out_file),
            ])
            assert result.exit_code == 0
            content = out_file.read_text()
            assert "Title,URL,Type,Creator,Category" in content
            assert "CSV Export" in content
            assert "AI Adoption" in content

    def test_export_list_category_filter(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        _add_sample(db, title="A", team_shareable=True, share_category="AI Adoption")
        _add_sample(db, title="B", team_shareable=True, share_category="Leadership")

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["media", "export-list", "--category", "Leadership", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert len(data) == 1
            assert data[0]["Title"] == "B"
