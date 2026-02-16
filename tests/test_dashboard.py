"""Tests for Beacon unified dashboard (Phase 5, Step 3)."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.dashboard import DashboardData, gather_dashboard_data
from beacon.dashboard_render import render_dashboard
from beacon.db.connection import get_connection, init_db

runner = CliRunner()


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


def _insert_company(conn, name="TestCo", score=8.0, tier=1):
    cursor = conn.execute(
        "INSERT INTO companies (name, careers_platform, domain, ai_first_score, tier) VALUES (?, 'greenhouse', 'testco.com', ?, ?)",
        (name, score, tier),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_job(conn, company_id, title="Data Engineer", score=8.0, status="active"):
    cursor = conn.execute(
        "INSERT INTO job_listings (company_id, title, relevance_score, status) VALUES (?, ?, ?, ?)",
        (company_id, title, score, status),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_application(conn, job_id, status="applied"):
    cursor = conn.execute(
        "INSERT INTO applications (job_id, status, applied_date) VALUES (?, ?, '2026-01-01')",
        (job_id, status),
    )
    conn.commit()
    return cursor.lastrowid


# --- Dashboard data gathering ---

class TestGatherDashboardData:
    def test_empty_db(self, db):
        conn, _ = db
        data = gather_dashboard_data(conn)
        assert data.company_count == 0
        assert data.active_job_count == 0
        assert data.application_count == 0
        # publications_talks has minimum=0, so 1/5 sections filled on empty DB = 20%
        assert data.profile_completeness == 20
        assert data.watchlist == []
        assert data.top_jobs == []
        assert data.pipeline == {}

    def test_with_companies(self, db):
        conn, _ = db
        _insert_company(conn, "Anthropic", 9.2, 1)
        _insert_company(conn, "Cursor", 8.8, 1)
        data = gather_dashboard_data(conn)
        assert data.company_count == 2
        assert len(data.watchlist) == 2
        assert data.watchlist[0]["name"] == "Anthropic"

    def test_with_jobs(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        _insert_job(conn, cid, "ML Engineer", 9.4)
        _insert_job(conn, cid, "Backend Dev", 6.5)
        data = gather_dashboard_data(conn)
        assert data.active_job_count == 2
        assert len(data.top_jobs) == 2
        assert data.top_jobs[0]["relevance_score"] == 9.4

    def test_with_applications(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        _insert_application(conn, jid, "applied")
        _insert_application(conn, jid, "draft")
        data = gather_dashboard_data(conn)
        assert data.application_count == 2
        assert data.pipeline.get("applied") == 1
        assert data.pipeline.get("draft") == 1

    def test_pipeline_counts(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        j1 = _insert_job(conn, cid, "Job A")
        j2 = _insert_job(conn, cid, "Job B")
        j3 = _insert_job(conn, cid, "Job C")
        _insert_application(conn, j1, "applied")
        _insert_application(conn, j2, "applied")
        _insert_application(conn, j3, "phone_screen")
        data = gather_dashboard_data(conn)
        assert data.pipeline["applied"] == 2
        assert data.pipeline["phone_screen"] == 1

    def test_watchlist_sorting(self, db):
        conn, _ = db
        _insert_company(conn, "Low", 3.0, 4)
        _insert_company(conn, "High", 9.5, 1)
        _insert_company(conn, "Mid", 6.0, 2)
        data = gather_dashboard_data(conn)
        assert data.watchlist[0]["name"] == "High"
        assert data.watchlist[1]["name"] == "Mid"
        assert data.watchlist[2]["name"] == "Low"

    def test_presence_health_empty(self, db):
        conn, _ = db
        data = gather_dashboard_data(conn)
        assert data.presence["profile_completeness"]["status"] == "red"
        assert data.presence["last_content"]["status"] == "red"

    def test_content_pipeline(self, db):
        conn, _ = db
        conn.execute(
            "INSERT INTO content_drafts (content_type, platform, title, body, status) VALUES ('post', 'blog', 'Test', 'body', 'draft')"
        )
        conn.commit()
        data = gather_dashboard_data(conn)
        assert data.content["drafts_ready"] == 1

    def test_feedback_summary(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        aid = _insert_application(conn, jid)
        conn.execute(
            "INSERT INTO application_outcomes (application_id, outcome) VALUES (?, 'phone_screen')",
            (aid,),
        )
        conn.execute(
            "INSERT INTO application_outcomes (application_id, outcome) VALUES (?, 'rejection_auto')",
            (aid,),
        )
        conn.commit()
        data = gather_dashboard_data(conn)
        assert data.feedback["total_outcomes"] == 2
        assert data.feedback["positive_outcomes"] == 1


class TestActionItems:
    def test_no_action_items_empty_db(self, db):
        conn, _ = db
        data = gather_dashboard_data(conn)
        assert data.action_items == []

    def test_stale_applications(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        # Create an old application
        conn.execute(
            "INSERT INTO applications (job_id, status, applied_date) VALUES (?, 'applied', '2025-12-01')",
            (jid,),
        )
        conn.commit()
        data = gather_dashboard_data(conn)
        assert any("Record outcome" in item for item in data.action_items)

    def test_overdue_calendar(self, db):
        conn, _ = db
        conn.execute(
            "INSERT INTO content_calendar (title, platform, content_type, target_date, status) VALUES ('Old post', 'blog', 'post', '2025-01-01', 'idea')"
        )
        conn.commit()
        data = gather_dashboard_data(conn)
        assert any("overdue" in item.lower() for item in data.action_items)


# --- Dashboard rendering ---

class TestDashboardRender:
    def test_render_plain(self, db, capsys):
        conn, _ = db
        _insert_company(conn, "Anthropic", 9.2)
        data = gather_dashboard_data(conn)
        render_dashboard(None, data)
        captured = capsys.readouterr()
        assert "Beacon Dashboard" in captured.out
        assert "1 companies" in captured.out

    def test_render_compact_plain(self, db, capsys):
        conn, _ = db
        data = gather_dashboard_data(conn)
        render_dashboard(None, data, compact=True)
        captured = capsys.readouterr()
        assert "Beacon Dashboard" in captured.out

    def test_render_with_rich(self, db):
        from rich.console import Console
        from io import StringIO
        conn, _ = db
        _insert_company(conn, "Anthropic", 9.2)
        cid = conn.execute("SELECT id FROM companies").fetchone()["id"]
        _insert_job(conn, cid, "ML Engineer", 9.0)
        data = gather_dashboard_data(conn)
        output = StringIO()
        test_console = Console(file=output, force_terminal=True)
        render_dashboard(test_console, data)
        result = output.getvalue()
        assert "Beacon Dashboard" in result

    def test_render_compact_with_rich(self, db):
        from rich.console import Console
        from io import StringIO
        conn, _ = db
        data = gather_dashboard_data(conn)
        output = StringIO()
        test_console = Console(file=output, force_terminal=True)
        render_dashboard(test_console, data, compact=True)
        # Should not error


# --- CLI ---

class TestDashboardCLI:
    def test_dashboard_command(self, db):
        from beacon.cli import app
        conn, db_path = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0

    def test_dashboard_compact(self, db):
        from beacon.cli import app
        conn, db_path = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["dashboard", "--compact"])
            assert result.exit_code == 0

    def test_dashboard_with_data(self, db):
        from beacon.cli import app
        conn, db_path = db
        _insert_company(conn, "TestCo", 8.0)
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0
