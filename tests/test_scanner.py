"""Tests for the scanner orchestrator."""

from unittest.mock import MagicMock, patch

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.scanner import ScanResult, scan_all, scan_company


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _insert_company(conn, name="TestCo", platform="greenhouse", domain="testco.com"):
    conn.execute(
        "INSERT INTO companies (name, domain, careers_platform, careers_url, remote_policy, size_bucket) "
        "VALUES (?, ?, ?, ?, 'hybrid', 'mid-200-1000')",
        (name, domain, platform, f"https://{domain}/careers"),
    )
    conn.commit()
    return conn.execute("SELECT * FROM companies WHERE name = ?", (name,)).fetchone()


MOCK_JOBS = [
    {
        "title": "Senior Data Engineer",
        "url": "https://testco.com/jobs/1",
        "location": "Remote",
        "department": "Engineering",
        "description_text": "Build data pipelines with python, sql, and dbt.",
        "date_posted": "2025-03-01",
    },
    {
        "title": "Office Manager",
        "url": "https://testco.com/jobs/2",
        "location": "NYC",
        "department": "Operations",
        "description_text": "Manage the office.",
        "date_posted": "2025-03-01",
    },
]


class TestScanCompany:
    @patch("beacon.scanner.get_adapter")
    def test_scan_with_mocked_adapter(self, mock_get_adapter, db):
        company = _insert_company(db)
        mock_adapter = MagicMock()
        mock_adapter.fetch_jobs.return_value = MOCK_JOBS
        mock_get_adapter.return_value = mock_adapter

        result = scan_company(db, company)
        assert isinstance(result, ScanResult)
        assert result.jobs_found == 2
        assert result.new_jobs == 2
        assert result.error is None

        # Verify jobs in DB
        jobs = db.execute("SELECT * FROM job_listings ORDER BY relevance_score DESC").fetchall()
        assert len(jobs) == 2
        assert jobs[0]["relevance_score"] > jobs[1]["relevance_score"]

    @patch("beacon.scanner.get_adapter")
    def test_scan_unknown_platform(self, mock_get_adapter, db):
        company = _insert_company(db, platform="workday")
        mock_get_adapter.return_value = None

        result = scan_company(db, company)
        assert result.error is not None
        assert "No adapter" in result.error

    @patch("beacon.scanner.get_adapter")
    def test_scan_http_error(self, mock_get_adapter, db):
        company = _insert_company(db)
        mock_adapter = MagicMock()
        mock_adapter.fetch_jobs.side_effect = Exception("Connection timeout")
        mock_get_adapter.return_value = mock_adapter

        result = scan_company(db, company)
        assert result.error == "Connection timeout"
        assert result.jobs_found == 0

    @patch("beacon.scanner.get_adapter")
    def test_scan_marks_stale_jobs(self, mock_get_adapter, db):
        company = _insert_company(db)
        mock_adapter = MagicMock()
        mock_get_adapter.return_value = mock_adapter

        # First scan: two jobs
        mock_adapter.fetch_jobs.return_value = MOCK_JOBS
        scan_company(db, company)

        # Second scan: only one job
        mock_adapter.fetch_jobs.return_value = [MOCK_JOBS[0]]
        result = scan_company(db, company)
        assert result.stale_jobs == 1

        closed = db.execute("SELECT COUNT(*) as cnt FROM job_listings WHERE status = 'closed'").fetchone()["cnt"]
        assert closed == 1

    @patch("beacon.scanner.get_adapter")
    def test_rescan_updates_existing(self, mock_get_adapter, db):
        company = _insert_company(db)
        mock_adapter = MagicMock()
        mock_adapter.fetch_jobs.return_value = MOCK_JOBS
        mock_get_adapter.return_value = mock_adapter

        r1 = scan_company(db, company)
        assert r1.new_jobs == 2

        r2 = scan_company(db, company)
        assert r2.new_jobs == 0
        assert r2.updated_jobs == 2

    @patch("beacon.scanner.get_adapter")
    def test_empty_scan(self, mock_get_adapter, db):
        company = _insert_company(db)
        mock_adapter = MagicMock()
        mock_adapter.fetch_jobs.return_value = []
        mock_get_adapter.return_value = mock_adapter

        result = scan_company(db, company)
        assert result.jobs_found == 0
        assert result.new_jobs == 0


class TestScanAll:
    @patch("beacon.scanner.get_adapter")
    def test_scan_all_companies(self, mock_get_adapter, db):
        _insert_company(db, "CompanyA", domain="a.com")
        _insert_company(db, "CompanyB", domain="b.com")

        mock_adapter = MagicMock()
        mock_adapter.fetch_jobs.return_value = MOCK_JOBS
        mock_get_adapter.return_value = mock_adapter

        results = scan_all(db)
        assert len(results) == 2

    @patch("beacon.scanner.get_adapter")
    def test_scan_all_filters_by_platform(self, mock_get_adapter, db):
        _insert_company(db, "GH Co", platform="greenhouse", domain="gh.com")
        _insert_company(db, "Custom Co", platform="custom", domain="custom.com")

        mock_adapter = MagicMock()
        mock_adapter.fetch_jobs.return_value = []
        mock_get_adapter.return_value = mock_adapter

        results = scan_all(db, platform="greenhouse")
        assert len(results) == 1
        assert results[0].company_name == "GH Co"
