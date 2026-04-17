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
        assert result.exit_code == 2
        assert "No job found" in result.output

    @patch("beacon.cli.get_connection")
    def test_job_add_existing_company(self, mock_get_conn, db):
        conn, db_path = db
        _insert_company(conn, "Acme AI")
        mock_get_conn.return_value = conn

        result = runner.invoke(app, [
            "job", "add",
            "--title", "Senior Agent Engineer",
            "--company", "Acme AI",
            "--url", "https://acme.example.com/jobs/42",
            "--location", "Remote",
            "--description", "Build agents using python and LLMs.",
        ])
        assert result.exit_code == 0
        assert "Added job" in result.output
        verify = get_connection(db_path)
        row = verify.execute(
            "SELECT title, location, company_id FROM job_listings WHERE url = ?",
            ("https://acme.example.com/jobs/42",),
        ).fetchone()
        verify.close()
        assert row is not None
        assert row["title"] == "Senior Agent Engineer"
        assert row["location"] == "Remote"

    @patch("beacon.cli.get_connection")
    def test_job_add_missing_company_errors(self, mock_get_conn, db):
        conn, db_path = db
        mock_get_conn.return_value = conn

        result = runner.invoke(app, [
            "job", "add",
            "--title", "ML Engineer",
            "--company", "NoSuchCo",
        ])
        assert result.exit_code == 2
        assert "No company found" in result.output
        verify = get_connection(db_path)
        count = verify.execute("SELECT COUNT(*) as c FROM job_listings").fetchone()["c"]
        verify.close()
        assert count == 0

    @patch("beacon.cli.get_connection")
    def test_job_add_create_company(self, mock_get_conn, db):
        conn, db_path = db
        mock_get_conn.return_value = conn

        result = runner.invoke(app, [
            "job", "add",
            "--title", "Staff Engineer",
            "--company", "BrandNewCo",
            "--url", "https://brand.example.com/1",
            "--create-company",
        ])
        assert result.exit_code == 0
        assert "Created company" in result.output
        verify = get_connection(db_path)
        c = verify.execute("SELECT id, tier FROM companies WHERE name = ?", ("BrandNewCo",)).fetchone()
        j = verify.execute(
            "SELECT id FROM job_listings WHERE url = ?",
            ("https://brand.example.com/1",),
        ).fetchone()
        verify.close()
        assert c is not None
        assert c["tier"] == 4
        assert j is not None

    @patch("beacon.cli.get_connection")
    def test_job_add_json_output(self, mock_get_conn, db):
        conn, db_path = db
        _insert_company(conn, "Acme AI")
        mock_get_conn.return_value = conn

        result = runner.invoke(app, [
            "job", "add",
            "--title", "Data Engineer",
            "--company", "Acme AI",
            "--url", "https://acme.example.com/jobs/9",
            "--json",
        ])
        assert result.exit_code == 0
        import json as _json
        data = _json.loads(result.stdout)
        assert data["is_new"] is True
        assert data["company"] == "Acme AI"
        assert data["company_created"] is False
        assert data["title"] == "Data Engineer"
        assert "relevance_score" in data

    @patch("beacon.cli.get_connection")
    def test_job_add_fetch_requires_url(self, mock_get_conn, db):
        conn, _ = db
        mock_get_conn.return_value = conn

        result = runner.invoke(app, ["job", "add", "--fetch"])
        assert result.exit_code == 1
        assert "--fetch requires --url" in result.output

    @patch("beacon.research.job_fetcher.fetch_job_from_url")
    @patch("beacon.cli.get_connection")
    def test_job_add_fetch_extracts_fields(self, mock_get_conn, mock_fetch, db):
        conn, db_path = db
        _insert_company(conn, "Acme AI")
        mock_get_conn.return_value = conn
        mock_fetch.return_value = {
            "title": "Staff ML Engineer",
            "company": "Acme AI",
            "url": "https://boards.greenhouse.io/acme/jobs/99",
            "location": "Remote, US",
            "department": "Research",
            "description_text": "Build agent infrastructure with Python and LLMs.",
            "date_posted": "2026-04-01",
            "platform": "greenhouse",
        }

        result = runner.invoke(app, [
            "job", "add",
            "--fetch",
            "--url", "https://boards.greenhouse.io/acme/jobs/99",
            "--json",
        ])
        assert result.exit_code == 0, result.output
        import json as _json
        data = _json.loads(result.stdout)
        assert data["title"] == "Staff ML Engineer"
        assert data["company"] == "Acme AI"
        assert data["fetched"] is True
        assert data["platform"] == "greenhouse"
        assert data["is_new"] is True

        verify = get_connection(db_path)
        row = verify.execute(
            "SELECT title, location, department, description_text, date_posted "
            "FROM job_listings WHERE url = ?",
            ("https://boards.greenhouse.io/acme/jobs/99",),
        ).fetchone()
        verify.close()
        assert row["title"] == "Staff ML Engineer"
        assert row["location"] == "Remote, US"
        assert row["department"] == "Research"
        assert "agent infrastructure" in row["description_text"]
        assert row["date_posted"] == "2026-04-01"

    @patch("beacon.research.job_fetcher.fetch_job_from_url")
    @patch("beacon.cli.get_connection")
    def test_job_add_fetch_cli_overrides_extracted(self, mock_get_conn, mock_fetch, db):
        conn, _ = db
        _insert_company(conn, "Acme AI")
        mock_get_conn.return_value = conn
        mock_fetch.return_value = {
            "title": "Extracted Title",
            "company": "Acme AI",
            "url": "https://x.com/1",
            "location": "Remote",
            "department": None,
            "description_text": "Extracted body.",
            "date_posted": None,
            "platform": None,
        }

        result = runner.invoke(app, [
            "job", "add",
            "--fetch",
            "--url", "https://x.com/1",
            "--title", "Overridden Title",
            "--json",
        ])
        assert result.exit_code == 0, result.output
        import json as _json
        data = _json.loads(result.stdout)
        assert data["title"] == "Overridden Title"

    @patch("beacon.research.job_fetcher.fetch_job_from_url")
    @patch("beacon.cli.get_connection")
    def test_job_add_fetch_missing_title_errors(self, mock_get_conn, mock_fetch, db):
        conn, _ = db
        mock_get_conn.return_value = conn
        mock_fetch.return_value = {
            "title": "",
            "company": "",
            "url": "https://x.com/1",
            "location": "",
            "department": "",
            "description_text": "",
            "date_posted": None,
            "platform": None,
        }

        result = runner.invoke(app, [
            "job", "add",
            "--fetch",
            "--url", "https://x.com/1",
        ])
        assert result.exit_code == 1
        assert "Missing required field" in result.output

    @patch("beacon.research.job_fetcher.fetch_job_from_url")
    @patch("beacon.cli.get_connection")
    def test_job_add_fetch_network_error(self, mock_get_conn, mock_fetch, db):
        conn, _ = db
        mock_get_conn.return_value = conn
        mock_fetch.side_effect = RuntimeError("connection refused")

        result = runner.invoke(app, [
            "job", "add",
            "--fetch",
            "--url", "https://x.com/1",
            "--json",
        ])
        assert result.exit_code == 1
        import json as _json
        data = _json.loads(result.stdout)
        assert "Failed to fetch" in data["error"]


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
