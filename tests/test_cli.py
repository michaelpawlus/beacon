"""Tests for the Beacon CLI commands (Phase 2)."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from beacon.cli import app
from beacon.db.connection import get_connection, init_db
from beacon.db.jobs import upsert_job

runner = CliRunner()


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


def _insert_company(conn, name="TestCo", platform="greenhouse", domain="testco.com"):
    conn.execute(
        "INSERT INTO companies (name, domain, careers_platform, careers_url, remote_policy, size_bucket) "
        "VALUES (?, ?, ?, ?, 'hybrid', 'mid-200-1000')",
        (name, domain, platform, f"https://{domain}/careers"),
    )
    conn.commit()
    return conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()["id"]


class TestScanCommand:
    @patch("beacon.cli.get_connection")
    @patch("beacon.scanner.get_adapter")
    def test_scan_runs(self, mock_get_adapter, mock_get_conn, db):
        conn, db_path = db
        _insert_company(conn, "TestCo")
        mock_get_conn.return_value = conn

        mock_adapter = MagicMock()
        mock_adapter.fetch_jobs.return_value = [
            {"title": "Data Engineer", "url": "https://test.com/1", "location": "Remote",
             "department": "Eng", "description_text": "python sql", "date_posted": "2025-01-01"},
        ]
        mock_get_adapter.return_value = mock_adapter

        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "Scan" in result.output or "Total" in result.output


class TestJobsCommand:
    @patch("beacon.cli.get_connection")
    def test_jobs_list(self, mock_get_conn, db):
        conn, db_path = db
        cid = _insert_company(conn)
        upsert_job(conn, cid, "Data Engineer", url="https://x.com/1", relevance_score=8.5)
        upsert_job(conn, cid, "Office Manager", url="https://x.com/2", relevance_score=1.0)
        mock_get_conn.return_value = conn

        result = runner.invoke(app, ["jobs"])
        assert result.exit_code == 0
        assert "Data Engineer" in result.output

    @patch("beacon.cli.get_connection")
    def test_jobs_filter_by_status(self, mock_get_conn, db):
        conn, db_path = db
        cid = _insert_company(conn)
        r = upsert_job(conn, cid, "Applied Job", url="https://x.com/1", relevance_score=7.0)
        conn.execute("UPDATE job_listings SET status = 'applied' WHERE id = ?", (r["id"],))
        conn.commit()
        upsert_job(conn, cid, "Active Job", url="https://x.com/2", relevance_score=5.0)
        mock_get_conn.return_value = conn

        result = runner.invoke(app, ["jobs", "--status", "applied"])
        assert result.exit_code == 0
        assert "Applied Job" in result.output

    @patch("beacon.cli.get_connection")
    def test_jobs_no_results(self, mock_get_conn, db):
        conn, db_path = db
        mock_get_conn.return_value = conn

        result = runner.invoke(app, ["jobs"])
        assert result.exit_code == 0
        assert "No jobs found" in result.output


class TestJobSubcommands:
    @patch("beacon.cli.get_connection")
    def test_job_show(self, mock_get_conn, db):
        conn, db_path = db
        cid = _insert_company(conn)
        r = upsert_job(conn, cid, "ML Engineer", url="https://x.com/1", relevance_score=9.0,
                        location="Remote", match_reasons=["title_match:ml engineer"])
        mock_get_conn.return_value = conn

        result = runner.invoke(app, ["job", "show", str(r["id"])])
        assert result.exit_code == 0
        assert "ML Engineer" in result.output

    @patch("beacon.cli.get_connection")
    def test_job_apply(self, mock_get_conn, db):
        conn, db_path = db
        cid = _insert_company(conn)
        r = upsert_job(conn, cid, "Data Analyst", url="https://x.com/1")
        mock_get_conn.return_value = conn

        result = runner.invoke(app, ["job", "apply", str(r["id"])])
        assert result.exit_code == 0
        assert "applied" in result.output

    @patch("beacon.cli.get_connection")
    def test_job_ignore(self, mock_get_conn, db):
        conn, db_path = db
        cid = _insert_company(conn)
        r = upsert_job(conn, cid, "Recruiter", url="https://x.com/1")
        mock_get_conn.return_value = conn

        result = runner.invoke(app, ["job", "ignore", str(r["id"])])
        assert result.exit_code == 0
        assert "ignored" in result.output

    @patch("beacon.cli.get_connection")
    def test_job_show_not_found(self, mock_get_conn, db):
        conn, db_path = db
        mock_get_conn.return_value = conn

        result = runner.invoke(app, ["job", "show", "99999"])
        assert result.exit_code == 0
        assert "No job found" in result.output


class TestStatsWithJobs:
    @patch("beacon.cli.get_connection")
    def test_stats_shows_job_counts(self, mock_get_conn, db):
        conn, db_path = db
        cid = _insert_company(conn)
        upsert_job(conn, cid, "Job A", url="https://x.com/a", relevance_score=8.0)
        upsert_job(conn, cid, "Job B", url="https://x.com/b", relevance_score=3.0)
        mock_get_conn.return_value = conn

        result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0
        assert "Job Listings" in result.output
        assert "2 total" in result.output
